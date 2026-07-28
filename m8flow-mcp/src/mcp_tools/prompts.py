"""MCP Prompts for m8flow - Pre-built conversation templates.

Prompts are reusable conversation starters that guide users through
common m8flow workflows. They combine resources and tools into
guided experiences.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_prompts(mcp: "FastMCP") -> None:
    """Register all m8flow prompts with the MCP server.

    Prompts are conversation templates that guide users through
    common workflows by combining resources and tools.
    """

    @mcp.prompt(description="Browse and explore available workflow templates")
    def browse_workflows() -> str:
        """Browse all available workflows organized by category."""
        return """Show me all available workflows in m8flow.

Please read the discovery://workflows resource and show me:
1. All workflow categories
2. Workflow names and descriptions
3. Which ones are executable

Format the results in a clear, organized way."""

    @mcp.prompt(description="Start a new workflow instance (guided)")
    def start_workflow(workflow_id: str = "") -> str:
        """Start a new workflow instance with guided steps.

        Args:
            workflow_id: Process model identifier (e.g., 'demo-group/approval'). Leave empty to browse first.
        """
        workflow_ref = workflow_id if workflow_id else "a workflow_id we agree on"
        return f"""I want to start a new workflow instance.

Please help me:
1. If I haven't specified a workflow_id, show me available workflows using discovery://workflows
2. Once we have a workflow_id, start it using start_process_instance tool for {workflow_ref}
3. After starting, show me the workflow status using the workflow://{{instance_id}} resource
4. Tell me what tasks are waiting

Walk me through this step by step."""

    @mcp.prompt(description="View all my pending tasks")
    def check_my_tasks() -> str:
        """View and manage my pending tasks."""
        return """Show me all my pending tasks.

Please:
1. Read discovery://tasks resource to get task overview
2. Show me each task with:
   - Task name
   - Which workflow it belongs to
   - When it was created
   - What action is needed

If I have many tasks, organize them by workflow."""

    @mcp.prompt(description="Complete a task (guided)")
    def complete_task(process_instance_id: str = "", task_id: str = "") -> str:
        """Complete a workflow task with guided steps.

        Args:
            process_instance_id: Workflow instance ID. Leave empty to browse pending tasks first.
            task_id: Task ID or name. Leave empty to browse pending tasks first.
        """
        if process_instance_id and task_id:
            task_ref = f"task {task_id} on workflow instance {process_instance_id}"
        else:
            task_ref = "a task we identify together"
        return f"""I want to complete a workflow task ({task_ref}).

Please help me:
1. If I haven't specified which task, read discovery://tasks to show available tasks
2. Once we identify the task, read task://{{process_instance_id}}/{{task_id}} to see details
3. Ask me for any required data
4. Complete the task using complete_task tool
5. Show updated workflow status using workflow://{{process_instance_id}}

Guide me through this process."""

    @mcp.prompt(description="Check workflow instance status")
    def workflow_status(instance_id: str) -> str:
        """Check the status of a workflow instance.

        Args:
            instance_id: Workflow instance ID.
        """
        return f"""Show me the status of workflow instance {instance_id}.

Please:
1. Read workflow://{instance_id} resource
2. Show me:
   - Current status
   - Started when
   - Current step/task
   - What's waiting for action
   - Recent activity

Format it in a clear, easy-to-understand way."""

    @mcp.prompt(description="Understand workflow design and structure")
    def understand_bpmn(model_id: str = "") -> str:
        """Understand how a workflow is designed.

        Args:
            model_id: Process model identifier (e.g., 'demo-group/approval'). Leave empty to browse first.
        """
        model_ref = model_id if model_id else "a model_id we agree on"
        return f"""Explain how the workflow {model_ref} works.

Please:
1. If model_id not specified, show available workflows from discovery://workflows
2. Read bpmn://{{model_id}} resource to see the workflow definition
3. Explain:
   - What this workflow does
   - What are the main steps
   - What decisions are made
   - What tasks require human action
   - What happens automatically

Explain it in simple terms, like you're teaching someone who's never seen BPMN."""

    @mcp.prompt(description="Create a new workflow template")
    def create_workflow() -> str:
        """Create a new workflow template (guided)."""
        return """I want to create a new workflow template.

Please help me:
1. First, show me existing process groups using list_process_groups tool
2. Ask me:
   - Should I use an existing group or create a new one?
   - What should the workflow be called?
   - What should it do?
3. Guide me through creating the process model
4. Show me next steps for adding BPMN definition

Walk me through this step by step."""

    @mcp.prompt(description="Troubleshoot workflow issues")
    def troubleshoot_workflow(instance_id: str) -> str:
        """Troubleshoot a stuck or failing workflow.

        Args:
            instance_id: Workflow instance ID that has issues.
        """
        return f"""Help me troubleshoot workflow instance {instance_id}.

Please investigate:
1. Read workflow://{instance_id} to see current state
2. Check for:
   - Is it stuck? Where?
   - Are there errors?
   - What tasks are waiting?
   - How long has it been in this state?
3. Read bpmn:// for the model to understand what should happen
4. Suggest possible solutions:
   - What actions can I take?
   - What might be blocking it?
   - Should I complete a task manually?

Give me a clear diagnosis and action plan."""
