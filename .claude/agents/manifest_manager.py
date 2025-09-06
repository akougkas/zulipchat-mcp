#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Manifest Management System for WARP Framework Agent Outputs

This system manages the persistent memory and output tracking for multi-agent workflows,
ensuring that all agent interactions, outputs, and decisions are properly documented
and can be referenced in future operations.
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
import hashlib
import shutil

class WorkflowPhase(Enum):
    """Workflow execution phases."""
    RESEARCH = "research"
    DESIGN = "design" 
    IMPLEMENTATION = "implementation"
    VALIDATION = "validation"
    DEPLOYMENT = "deployment"

class AgentStatus(Enum):
    """Agent execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class AgentExecution:
    """Record of individual agent execution."""
    agent_name: str
    task_description: str
    status: AgentStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    output_files: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    token_usage: Dict[str, int] = field(default_factory=dict)
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_completed(self, output_files: List[str] = None, metadata: Dict[str, Any] = None):
        """Mark agent execution as completed."""
        self.end_time = datetime.now(timezone.utc)
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.status = AgentStatus.COMPLETED
        if output_files:
            self.output_files.extend(output_files)
        if metadata:
            self.metadata.update(metadata)
    
    def mark_failed(self, error_message: str, metadata: Dict[str, Any] = None):
        """Mark agent execution as failed."""
        self.end_time = datetime.now(timezone.utc) 
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.status = AgentStatus.FAILED
        self.error_message = error_message
        if metadata:
            self.metadata.update(metadata)

@dataclass
class PhaseExecution:
    """Record of workflow phase execution."""
    phase: WorkflowPhase
    status: AgentStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    agents: List[AgentExecution] = field(default_factory=list)
    phase_outputs: Dict[str, Any] = field(default_factory=dict)
    success_criteria_met: bool = False
    parallel_execution: bool = False
    
    def add_agent(self, agent_execution: AgentExecution):
        """Add agent execution to this phase."""
        self.agents.append(agent_execution)
    
    def mark_completed(self, success_criteria_met: bool = True):
        """Mark phase as completed."""
        self.end_time = datetime.now(timezone.utc)
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.status = AgentStatus.COMPLETED
        self.success_criteria_met = success_criteria_met

@dataclass
class WorkflowManifest:
    """Complete manifest for a multi-agent workflow operation."""
    
    # Basic identification
    operation_id: str
    workflow_name: str
    user_request: str
    
    # Timing
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    
    # Status tracking
    current_phase: Optional[WorkflowPhase] = None
    overall_status: AgentStatus = AgentStatus.PENDING
    
    # Execution tracking
    phases: List[PhaseExecution] = field(default_factory=list)
    
    # Context and variables
    initial_context: Dict[str, Any] = field(default_factory=dict)
    workflow_variables: Dict[str, Any] = field(default_factory=dict)
    
    # Outputs and artifacts
    output_directory: str = ""
    generated_files: List[str] = field(default_factory=list)
    archived_files: List[str] = field(default_factory=list)
    
    # Metrics and costs
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Decision tracking
    architectural_decisions: List[Dict[str, Any]] = field(default_factory=list)
    dependency_decisions: List[Dict[str, Any]] = field(default_factory=list)
    pattern_decisions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Quality metrics
    test_coverage: Optional[float] = None
    code_quality_score: Optional[float] = None
    security_scan_results: Dict[str, Any] = field(default_factory=dict)
    
    # Version and provenance
    manifest_version: str = "1.0"
    claude_version: str = "sonnet-4"
    framework_version: str = "WARP-1.0"
    
    def add_phase(self, phase: PhaseExecution):
        """Add phase execution to manifest."""
        self.phases.append(phase)
        self.current_phase = phase.phase
    
    def get_phase(self, phase: WorkflowPhase) -> Optional[PhaseExecution]:
        """Get specific phase execution."""
        for p in self.phases:
            if p.phase == phase:
                return p
        return None
    
    def mark_started(self):
        """Mark workflow as started."""
        self.started_at = datetime.now(timezone.utc)
        self.overall_status = AgentStatus.IN_PROGRESS
    
    def mark_completed(self, success: bool = True):
        """Mark workflow as completed."""
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.total_duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.overall_status = AgentStatus.COMPLETED if success else AgentStatus.FAILED
        self.current_phase = None

class ManifestManager:
    """Manages workflow manifests and agent output tracking."""
    
    def __init__(self, base_output_dir: str = "~/.claude/outputs"):
        self.base_output_dir = Path(base_output_dir).expanduser()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        self.active_manifests: Dict[str, WorkflowManifest] = {}
        self.manifest_cache: Dict[str, WorkflowManifest] = {}
    
    def create_manifest(
        self,
        workflow_name: str,
        user_request: str,
        initial_context: Dict[str, Any] = None,
        workflow_variables: Dict[str, Any] = None
    ) -> WorkflowManifest:
        """Create new workflow manifest."""
        
        operation_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Create output directory
        output_dir_name = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{workflow_name.replace(' ', '_')}"
        output_directory = self.base_output_dir / output_dir_name
        output_directory.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        for subdir in ["research", "design", "implementation", "validation", "deployment"]:
            (output_directory / subdir).mkdir(exist_ok=True)
        
        manifest = WorkflowManifest(
            operation_id=operation_id,
            workflow_name=workflow_name,
            user_request=user_request,
            created_at=timestamp,
            initial_context=initial_context or {},
            workflow_variables=workflow_variables or {},
            output_directory=str(output_directory)
        )
        
        # Save manifest
        self.save_manifest(manifest)
        self.active_manifests[operation_id] = manifest
        
        return manifest
    
    def start_phase(
        self,
        manifest: WorkflowManifest,
        phase: WorkflowPhase,
        parallel_execution: bool = False
    ) -> PhaseExecution:
        """Start a new workflow phase."""
        
        phase_execution = PhaseExecution(
            phase=phase,
            status=AgentStatus.IN_PROGRESS,
            start_time=datetime.now(timezone.utc),
            parallel_execution=parallel_execution
        )
        
        manifest.add_phase(phase_execution)
        
        # Mark workflow as started if this is the first phase
        if manifest.started_at is None:
            manifest.mark_started()
        
        self.save_manifest(manifest)
        return phase_execution
    
    def start_agent(
        self,
        manifest: WorkflowManifest,
        phase: WorkflowPhase,
        agent_name: str,
        task_description: str,
        metadata: Dict[str, Any] = None
    ) -> AgentExecution:
        """Start agent execution within a phase."""
        
        phase_execution = manifest.get_phase(phase)
        if not phase_execution:
            raise ValueError(f"Phase {phase} not found in manifest")
        
        agent_execution = AgentExecution(
            agent_name=agent_name,
            task_description=task_description,
            status=AgentStatus.IN_PROGRESS,
            start_time=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        phase_execution.add_agent(agent_execution)
        self.save_manifest(manifest)
        
        return agent_execution
    
    def complete_agent(
        self,
        manifest: WorkflowManifest,
        agent_execution: AgentExecution,
        output_files: List[str] = None,
        token_usage: Dict[str, int] = None,
        cost_usd: float = None,
        metadata: Dict[str, Any] = None
    ):
        """Mark agent execution as completed."""
        
        agent_execution.mark_completed(output_files, metadata)
        
        if token_usage:
            agent_execution.token_usage = token_usage
            manifest.total_tokens_used += sum(token_usage.values())
        
        if cost_usd:
            agent_execution.cost_usd = cost_usd
            manifest.total_cost_usd += cost_usd
        
        self.save_manifest(manifest)
    
    def complete_phase(
        self,
        manifest: WorkflowManifest,
        phase: WorkflowPhase,
        phase_outputs: Dict[str, Any] = None,
        success_criteria_met: bool = True
    ):
        """Mark phase as completed."""
        
        phase_execution = manifest.get_phase(phase)
        if not phase_execution:
            raise ValueError(f"Phase {phase} not found in manifest")
        
        if phase_outputs:
            phase_execution.phase_outputs = phase_outputs
        
        phase_execution.mark_completed(success_criteria_met)
        self.save_manifest(manifest)
    
    def complete_workflow(
        self,
        manifest: WorkflowManifest,
        success: bool = True,
        final_artifacts: List[str] = None,
        performance_metrics: Dict[str, Any] = None
    ):
        """Mark entire workflow as completed."""
        
        manifest.mark_completed(success)
        
        if final_artifacts:
            manifest.generated_files.extend(final_artifacts)
        
        if performance_metrics:
            manifest.performance_metrics.update(performance_metrics)
        
        # Remove from active manifests
        if manifest.operation_id in self.active_manifests:
            del self.active_manifests[manifest.operation_id]
        
        self.save_manifest(manifest)
        
        # Generate final report
        self.generate_workflow_report(manifest)
    
    def save_manifest(self, manifest: WorkflowManifest):
        """Save manifest to disk."""
        output_dir = Path(manifest.output_directory)
        manifest_file = output_dir / "manifest.json"
        
        # Convert dataclass to dict with datetime serialization
        manifest_dict = asdict(manifest)
        
        # Convert datetime objects to ISO format strings
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: serialize_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_datetime(item) for item in obj]
            elif hasattr(obj, 'value'):  # Enum
                return obj.value
            return obj
        
        serialized_manifest = serialize_datetime(manifest_dict)
        
        with open(manifest_file, 'w') as f:
            json.dump(serialized_manifest, f, indent=2, default=str)
    
    def load_manifest(self, operation_id: str) -> Optional[WorkflowManifest]:
        """Load manifest from disk."""
        if operation_id in self.manifest_cache:
            return self.manifest_cache[operation_id]
        
        # Search for manifest file in output directories
        for manifest_dir in self.base_output_dir.iterdir():
            if manifest_dir.is_dir():
                manifest_file = manifest_dir / "manifest.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r') as f:
                        data = json.load(f)
                        if data.get("operation_id") == operation_id:
                            # Convert back to WorkflowManifest (simplified)
                            # In practice, would need full deserialization
                            return data
        
        return None
    
    def find_manifests_by_criteria(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[AgentStatus] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Find manifests matching criteria."""
        manifests = []
        
        for manifest_dir in self.base_output_dir.iterdir():
            if manifest_dir.is_dir():
                manifest_file = manifest_dir / "manifest.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r') as f:
                        data = json.load(f)
                        
                        # Apply filters
                        if workflow_name and data.get("workflow_name") != workflow_name:
                            continue
                        
                        if status and data.get("overall_status") != status.value:
                            continue
                        
                        manifests.append(data)
        
        return manifests
    
    def generate_workflow_report(self, manifest: WorkflowManifest) -> str:
        """Generate comprehensive workflow report."""
        
        report_path = Path(manifest.output_directory) / "workflow_report.md"
        
        report_content = f"""
# Workflow Report: {manifest.workflow_name}

## Overview
- **Operation ID**: {manifest.operation_id}
- **User Request**: {manifest.user_request}
- **Status**: {manifest.overall_status.value}
- **Started**: {manifest.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if manifest.started_at else 'N/A'}
- **Completed**: {manifest.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if manifest.completed_at else 'N/A'}
- **Total Duration**: {manifest.total_duration_seconds:.2f} seconds ({manifest.total_duration_seconds/60:.1f} minutes)

## Resource Usage
- **Total Tokens**: {manifest.total_tokens_used:,}
- **Total Cost**: ${manifest.total_cost_usd:.4f}
- **Files Generated**: {len(manifest.generated_files)}

## Phase Execution Summary

"""
        
        for phase_exec in manifest.phases:
            report_content += f"""
### {phase_exec.phase.value.title()} Phase
- **Status**: {phase_exec.status.value}
- **Duration**: {phase_exec.duration_seconds:.2f}s
- **Agents**: {len(phase_exec.agents)}
- **Parallel Execution**: {'Yes' if phase_exec.parallel_execution else 'No'}
- **Success Criteria Met**: {'Yes' if phase_exec.success_criteria_met else 'No'}

#### Agent Executions:
"""
            
            for agent in phase_exec.agents:
                status_emoji = {"completed": "✅", "failed": "❌", "in_progress": "⏳"}.get(agent.status.value, "❓")
                report_content += f"- {status_emoji} **{agent.agent_name}**: {agent.task_description[:100]}...\n"
                report_content += f"  - Duration: {agent.duration_seconds:.2f}s\n"
                if agent.token_usage:
                    report_content += f"  - Tokens: {sum(agent.token_usage.values())}\n"
                if agent.cost_usd:
                    report_content += f"  - Cost: ${agent.cost_usd:.4f}\n"
                report_content += f"  - Outputs: {len(agent.output_files)} files\n"
        
        if manifest.architectural_decisions:
            report_content += f"""
## Architectural Decisions
"""
            for i, decision in enumerate(manifest.architectural_decisions, 1):
                report_content += f"{i}. {decision}\n"
        
        report_content += f"""
## Performance Metrics
{json.dumps(manifest.performance_metrics, indent=2) if manifest.performance_metrics else 'No metrics collected'}

## Generated Artifacts
"""
        
        for file_path in manifest.generated_files:
            report_content += f"- {file_path}\n"
        
        # Write report to file
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        return str(report_path)
    
    def cleanup_old_manifests(self, days_old: int = 30):
        """Clean up manifest directories older than specified days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        for manifest_dir in self.base_output_dir.iterdir():
            if manifest_dir.is_dir():
                manifest_file = manifest_dir / "manifest.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r') as f:
                        data = json.load(f)
                        created_at = datetime.fromisoformat(data.get("created_at", ""))
                        
                        if created_at < cutoff_date:
                            # Archive before deletion
                            self.archive_manifest_directory(manifest_dir)
                            shutil.rmtree(manifest_dir)
                            print(f"Cleaned up old manifest: {manifest_dir.name}")
    
    def archive_manifest_directory(self, manifest_dir: Path):
        """Archive manifest directory before cleanup."""
        archive_dir = self.base_output_dir.parent / "archives"
        archive_dir.mkdir(exist_ok=True)
        
        archive_name = f"{manifest_dir.name}.tar.gz"
        archive_path = archive_dir / archive_name
        
        shutil.make_archive(str(archive_path).replace('.tar.gz', ''), 'gztar', manifest_dir)

# Global manifest manager instance
manifest_manager = ManifestManager()

def create_workflow_manifest(workflow_name: str, user_request: str, **kwargs) -> WorkflowManifest:
    """Convenience function to create workflow manifest."""
    return manifest_manager.create_manifest(workflow_name, user_request, **kwargs)

def get_active_manifest(operation_id: str) -> Optional[WorkflowManifest]:
    """Get active manifest by operation ID."""
    return manifest_manager.active_manifests.get(operation_id)