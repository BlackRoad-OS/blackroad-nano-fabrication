#!/usr/bin/env python3
"""
BlackRoad Nano-Fabrication
Nano-fabrication process controller and layer stack simulator.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FabProcess:
    """Represents a fabrication process."""
    id: str
    name: str
    type: str
    material: str
    layer_nm: float
    temperature_c: float
    pressure_torr: float
    duration_s: float
    status: str
    substrate: str
    created_at: str


@dataclass
class FabLayer:
    """Represents a fabricated layer."""
    process_id: str
    layer_num: int
    thickness_nm: float
    uniformity_pct: float
    defect_density: float


class NanoFabController:
    """Nano-fabrication process controller."""

    VALID_TYPES = [
        "cvd", "pvd", "ald", "lithography", "etching",
        "doping", "annealing", "cleaning"
    ]
    
    MATERIALS = [
        "silicon", "germanium", "gallium_arsenide",
        "silicon_dioxide", "hafnium_oxide", "titanium_nitride",
        "copper", "aluminum"
    ]

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the nano-fabrication controller."""
        if db_path is None:
            db_path = os.path.expanduser("~/.blackroad/nanofab.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.processes: Dict[str, FabProcess] = {}
        self.stacks: Dict[str, List[FabLayer]] = {}
        self._init_db()
        self._load_processes()

    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS processes
                     (id TEXT PRIMARY KEY, name TEXT, type TEXT, material TEXT,
                      layer_nm REAL, temperature_c REAL, pressure_torr REAL,
                      duration_s REAL, status TEXT, substrate TEXT, created_at TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS layers
                     (id INTEGER PRIMARY KEY, process_id TEXT, layer_num INTEGER,
                      thickness_nm REAL, uniformity_pct REAL, defect_density REAL,
                      FOREIGN KEY(process_id) REFERENCES processes(id))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS stacks
                     (id TEXT PRIMARY KEY, process_ids TEXT, total_thickness_nm REAL,
                      conductivity_estimate REAL, stress_estimate REAL, created_at TEXT)''')
        
        conn.commit()
        conn.close()

    def _load_processes(self):
        """Load processes from database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM processes")
        for row in c.fetchall():
            proc = FabProcess(
                id=row[0], name=row[1], type=row[2], material=row[3],
                layer_nm=row[4], temperature_c=row[5], pressure_torr=row[6],
                duration_s=row[7], status=row[8], substrate=row[9], created_at=row[10]
            )
            self.processes[proc.id] = proc
        
        conn.close()

    def create_process(self, name: str, process_type: str, material: str,
                      layer_nm: float, temperature_c: float, pressure_torr: float,
                      duration_s: float, substrate: str = "silicon") -> str:
        """Create a new fabrication process."""
        if process_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid process type: {process_type}")
        if material not in self.MATERIALS:
            raise ValueError(f"Invalid material: {material}")
        
        proc_id = f"{process_type}_{len(self.processes)}_{int(datetime.now().timestamp())}"
        now = datetime.now().isoformat()
        
        proc = FabProcess(
            id=proc_id,
            name=name,
            type=process_type,
            material=material,
            layer_nm=layer_nm,
            temperature_c=temperature_c,
            pressure_torr=pressure_torr,
            duration_s=duration_s,
            status="created",
            substrate=substrate,
            created_at=now,
        )
        
        self.processes[proc_id] = proc
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            '''INSERT INTO processes 
               (id, name, type, material, layer_nm, temperature_c, pressure_torr,
                duration_s, status, substrate, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (proc.id, proc.name, proc.type, proc.material, proc.layer_nm,
             proc.temperature_c, proc.pressure_torr, proc.duration_s,
             proc.status, proc.substrate, proc.created_at)
        )
        conn.commit()
        conn.close()
        
        return proc_id

    def run_process(self, process_id: str) -> FabLayer:
        """Simulate a fabrication process run."""
        proc = self.processes[process_id]
        
        # Simulate process results based on type and parameters
        uniformity = 98.5 - (proc.temperature_c - 300) / 100
        uniformity = max(90.0, min(99.9, uniformity))
        
        defect_density = 0.05 + (proc.pressure_torr - 100) / 1000
        defect_density = max(0.01, min(0.5, defect_density))
        
        thickness = proc.layer_nm * (1.0 + (proc.duration_s - 60) / 1000)
        
        layer = FabLayer(
            process_id=process_id,
            layer_num=1,
            thickness_nm=thickness,
            uniformity_pct=uniformity,
            defect_density=defect_density,
        )
        
        proc.status = "completed"
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            '''INSERT INTO layers (process_id, layer_num, thickness_nm, uniformity_pct, defect_density)
               VALUES (?, ?, ?, ?, ?)''',
            (layer.process_id, layer.layer_num, layer.thickness_nm,
             layer.uniformity_pct, layer.defect_density)
        )
        c.execute("UPDATE processes SET status = ? WHERE id = ?",
                 ("completed", process_id))
        conn.commit()
        conn.close()
        
        return layer

    def stack_layers(self, process_ids: List[str]) -> str:
        """Build a layer stack from multiple processes."""
        if not process_ids:
            raise ValueError("Need at least one process")
        
        layers = []
        total_thickness = 0.0
        
        for i, proc_id in enumerate(process_ids):
            layer = self.run_process(proc_id)
            layer.layer_num = i + 1
            layers.append(layer)
            total_thickness += layer.thickness_nm
        
        stack_id = f"stack_{len(self.stacks)}_{int(datetime.now().timestamp())}"
        self.stacks[stack_id] = layers
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            '''INSERT INTO stacks (id, process_ids, total_thickness_nm, conductivity_estimate, stress_estimate, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (stack_id, json.dumps(process_ids), total_thickness, 1e-6, 100.0,
             datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        return stack_id

    def analyze_stack(self, stack_id: str) -> Dict:
        """Analyze a layer stack."""
        layers = self.stacks.get(stack_id, [])
        
        if not layers:
            raise ValueError(f"Stack {stack_id} not found")
        
        total_thickness = sum(l.thickness_nm for l in layers)
        avg_uniformity = sum(l.uniformity_pct for l in layers) / len(layers)
        total_defect = sum(l.defect_density for l in layers)
        
        # Conductivity estimate (simplified)
        conductivity = 1e-6 * avg_uniformity / 100.0
        
        # Stress estimate (MPa)
        stress = 100.0 * (1.0 - avg_uniformity / 100.0)
        
        return {
            "stack_id": stack_id,
            "num_layers": len(layers),
            "total_thickness_nm": total_thickness,
            "avg_uniformity_pct": avg_uniformity,
            "total_defect_density": total_defect,
            "conductivity_s_m": conductivity,
            "stress_mpa": stress,
        }

    def quality_check(self, process_id: str) -> bool:
        """Check if process meets quality standards."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            '''SELECT uniformity_pct, defect_density FROM layers
               WHERE process_id = ? ORDER BY layer_num DESC LIMIT 1''',
            (process_id,)
        )
        
        result = c.fetchone()
        conn.close()
        
        if not result:
            return False
        
        uniformity, defect_density = result
        return uniformity > 95.0 and defect_density < 0.1

    def get_process_params(self, process_id: str) -> Dict:
        """Get process parameters."""
        proc = self.processes[process_id]
        return {
            "id": proc.id,
            "name": proc.name,
            "type": proc.type,
            "material": proc.material,
            "layer_nm": proc.layer_nm,
            "temperature_c": proc.temperature_c,
            "pressure_torr": proc.pressure_torr,
            "duration_s": proc.duration_s,
            "status": proc.status,
            "substrate": proc.substrate,
            "created_at": proc.created_at,
        }

    def list_processes(self, process_type: Optional[str] = None,
                      material: Optional[str] = None) -> List[Dict]:
        """List processes with optional filters."""
        results = []
        
        for proc in self.processes.values():
            if process_type and proc.type != process_type:
                continue
            if material and proc.material != material:
                continue
            results.append(self.get_process_params(proc.id))
        
        return results

    def export_recipe(self, process_id: str) -> str:
        """Export process as YAML-formatted recipe."""
        proc = self.processes[process_id]
        
        yaml = f"""# Nano-Fabrication Recipe
process_id: {proc.id}
name: {proc.name}
type: {proc.type}
substrate: {proc.substrate}
material: {proc.material}

parameters:
  layer_thickness_nm: {proc.layer_nm}
  temperature_celsius: {proc.temperature_c}
  pressure_torr: {proc.pressure_torr}
  duration_seconds: {proc.duration_s}

status: {proc.status}
created_at: {proc.created_at}
"""
        return yaml


def main():
    """CLI interface."""
    import sys
    
    controller = NanoFabController()
    
    if len(sys.argv) < 2:
        print("Usage: nano_fab.py [list|create|run|stack|analyze|check|export]")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        process_type = sys.argv[2] if len(sys.argv) > 2 else None
        procs = controller.list_processes(process_type=process_type)
        print(f"Processes ({len(procs)}):")
        for proc in procs:
            print(f"  {proc['id'][:20]:20} {proc['type']:12} {proc['material']:20} {proc['status']}")
    
    elif command == "create" and len(sys.argv) >= 5:
        name = sys.argv[2]
        proc_type = sys.argv[3]
        material = sys.argv[4]
        proc_id = controller.create_process(name, proc_type, material, 10.0, 300, 100, 120)
        print(f"Created process: {proc_id}")
    
    elif command == "run" and len(sys.argv) >= 3:
        proc_id = sys.argv[2]
        layer = controller.run_process(proc_id)
        passed = controller.quality_check(proc_id)
        print(f"Process {proc_id} completed")
        print(f"  Thickness: {layer.thickness_nm:.2f} nm")
        print(f"  Uniformity: {layer.uniformity_pct:.1f}%")
        print(f"  Defect Density: {layer.defect_density:.4f}")
        print(f"  Quality Check: {'PASS' if passed else 'FAIL'}")
    
    elif command == "stack" and len(sys.argv) >= 3:
        proc_ids = sys.argv[2:]
        stack_id = controller.stack_layers(proc_ids)
        analysis = controller.analyze_stack(stack_id)
        print(f"Stack created: {stack_id}")
        print(f"  Total Thickness: {analysis['total_thickness_nm']:.2f} nm")
        print(f"  Layers: {analysis['num_layers']}")
    
    elif command == "analyze" and len(sys.argv) >= 3:
        stack_id = sys.argv[2]
        analysis = controller.analyze_stack(stack_id)
        print(f"Stack Analysis: {stack_id}")
        for key, value in analysis.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
    
    elif command == "check" and len(sys.argv) >= 3:
        proc_id = sys.argv[2]
        passed = controller.quality_check(proc_id)
        print(f"Quality Check: {'PASS' if passed else 'FAIL'}")
    
    elif command == "export" and len(sys.argv) >= 3:
        proc_id = sys.argv[2]
        yaml = controller.export_recipe(proc_id)
        print(yaml)
    
    else:
        print("Unknown command or invalid arguments")


if __name__ == "__main__":
    main()
