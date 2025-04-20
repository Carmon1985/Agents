# src/agents/simulation_agent.py

import logging
from typing import Optional, Dict, Any
import autogen
import json

logger = logging.getLogger(__name__) # Basic logging

class SimulationAgent(autogen.AssistantAgent):
    """An agent specialized in running what-if scenarios and simulations 
    based on resource utilization data.
    """
    def __init__(
        self,
        name: str = "SimulationAgent",
        llm_config: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None,
        **kwargs,
    ):
        """
        Args:
            name: The name of the agent.
            llm_config: Configuration for the language model.
            system_message: An optional system message to override the default.
            **kwargs: Additional arguments for the AssistantAgent.
        """
        
        default_system_message = (
            "You are the Simulation Agent. Your role is to execute what-if scenarios based on user requests. "
            "You will use provided tool functions to simulate changes to resources, targets, or other parameters. "
            "Analyze the inputs, call the appropriate simulation tools, and present the projected outcomes clearly, "
            "comparing them to the baseline or current state. Focus on quantifying the impact of the simulated changes."
            "\nAvailable tools:"
            "- simulate_resource_change: Models the impact of moving resources between projects/competencies."
            "- simulate_target_adjustment: Models the impact of changing utilization targets."
            "- calculate_projected_outcomes: Determines effects on key metrics based on simulation results."
            "\nExplain the simulation steps and the final projected impact clearly."
        )
        
        super().__init__(
            name=name,
            llm_config=llm_config,
            system_message=system_message or default_system_message,
            **kwargs,
        )
        
        logger.info(f"SimulationAgent '{name}' initialized.")

# --- Simulation Tool Functions --- 
# These will be implemented later and registered with the agent or a UserProxyAgent

def simulate_resource_change(
    resource_id: str,
    source_assignment: Dict[str, Any], # e.g., {"project_id": "P101", "allocated_hours": 20}
    target_assignment: Dict[str, Any], # e.g., {"project_id": "P202", "allocated_hours": 10}
    hours_to_move: float,
    timeframe_weeks: int = 4 # Default simulation timeframe (e.g., 4 weeks)
) -> Dict[str, Any]:
    """Simulates the impact of moving a resource's allocated hours between assignments.

    Args:
        resource_id: Identifier of the resource being moved.
        source_assignment: Dictionary describing the source assignment (project/team, current hours).
        target_assignment: Dictionary describing the target assignment (project/team, current hours).
        hours_to_move: The number of hours per week being moved.
        timeframe_weeks: The duration of the simulation in weeks.

    Returns:
        A dictionary containing the simulation results.
    """
    logger.info(f"Running simulation: Moving {hours_to_move} hrs/week for resource '{resource_id}' "
                f"from {source_assignment.get('project_id', 'source')} to {target_assignment.get('project_id', 'target')}"
                f" over {timeframe_weeks} weeks.")

    # --- Simulate Data Fetching (Replace with actual data access) ---
    # Assume a standard capacity per week for the resource
    resource_capacity_per_week = 40.0 
    # Baseline allocations (use provided or assume defaults)
    baseline_source_hours = source_assignment.get('allocated_hours', 0.0)
    baseline_target_hours = target_assignment.get('allocated_hours', 0.0)
    # Estimate 'other' hours based on a typical total allocation if not provided
    # This is a simplification - real implementation needs accurate baseline
    assumed_baseline_total = max(baseline_source_hours + baseline_target_hours, resource_capacity_per_week * 0.8) # Assume at least 80% baseline util
    baseline_other_hours = max(0.0, assumed_baseline_total - baseline_source_hours - baseline_target_hours)
    baseline_total_allocated = baseline_source_hours + baseline_target_hours + baseline_other_hours
    baseline_utilization = (baseline_total_allocated / resource_capacity_per_week) * 100 if resource_capacity_per_week > 0 else 0

    # --- Validate Inputs ---
    if not isinstance(hours_to_move, (int, float)) or hours_to_move <= 0:
        logger.error(f"Invalid hours_to_move: {hours_to_move}")
        return {"status": "error", "message": "Hours to move must be a positive number."}
    if hours_to_move > baseline_source_hours:
        logger.error(f"Attempted to move {hours_to_move} hrs, but only {baseline_source_hours} are allocated to source for {resource_id}")
        return {"status": "error", "message": f"Cannot move {hours_to_move} hours. Resource '{resource_id}' only has {baseline_source_hours:.1f} allocated to source assignment."}
    
    simulated_total_allocated = baseline_total_allocated # Starts same, change is neutral for total if just moving
    simulated_source_hours = baseline_source_hours - hours_to_move
    simulated_target_hours = baseline_target_hours + hours_to_move
    # Recalculate total in case 'other' hours need adjustment (e.g., if total goes over capacity)
    simulated_total_check = simulated_source_hours + simulated_target_hours + baseline_other_hours 

    if simulated_total_check > resource_capacity_per_week:
         logger.warning(f"Simulated total allocation ({simulated_total_check:.1f}) for resource '{resource_id}' exceeds capacity ({resource_capacity_per_week:.1f}). Clamping total allocation to capacity.")
         # How to handle over-capacity? Reduce 'other' hours first? For now, just cap utilization calc.
         simulated_total_allocated = resource_capacity_per_week 
    else:
        simulated_total_allocated = simulated_total_check
    
    # --- Perform Simulation Calculation ---
    simulated_utilization = (simulated_total_allocated / resource_capacity_per_week) * 100 if resource_capacity_per_week > 0 else 0
    utilization_change = simulated_utilization - baseline_utilization

    # --- Prepare Results ---
    results = {
        "status": "success",
        "simulation_type": "resource_change",
        "parameters": {
            "resource_id": resource_id,
            "source_assignment": source_assignment,
            "target_assignment": target_assignment,
            "hours_to_move": hours_to_move,
            "timeframe_weeks": timeframe_weeks
        },
        "baseline_state": {
            "source_hours": round(baseline_source_hours, 2),
            "target_hours": round(baseline_target_hours, 2),
            "other_hours": round(baseline_other_hours, 2),
            "total_allocated_hours": round(baseline_total_allocated, 2),
            "utilization_percent": round(baseline_utilization, 2)
        },
        "simulated_state": {
            "source_hours": round(simulated_source_hours, 2),
            "target_hours": round(simulated_target_hours, 2),
            "other_hours": round(baseline_other_hours, 2),
            "total_allocated_hours": round(simulated_total_allocated, 2),
            "utilization_percent": round(simulated_utilization, 2)
        },
        "impact": {
            "utilization_change_percent": round(utilization_change, 2),
            "baseline_utilization_percent": round(baseline_utilization, 2),
            "simulated_utilization_percent": round(simulated_utilization, 2),
            "baseline_source_hours": round(baseline_source_hours, 2),
            "simulated_source_hours": round(simulated_source_hours, 2),
            "baseline_target_hours": round(baseline_target_hours, 2),
            "simulated_target_hours": round(simulated_target_hours, 2)
            # TODO: Add potential cost impact, project timeline impact etc. if data allows
        },
        "summary": f"Simulating moving {hours_to_move} hrs/wk for resource '{resource_id}' changes their projected utilization from {baseline_utilization:.1f}% to {simulated_utilization:.1f}%."
    }
    
    logger.info(f"Simulation complete for resource '{resource_id}'. Utilization change: {utilization_change:.2f}%.")
    return results

def simulate_target_adjustment(
    target_scope: str, # e.g., "global", "team", "resource", "project"
    current_target_utilization: float, # e.g., 80.0
    new_target_utilization: float, # e.g., 85.0
    scope_id: Optional[str] = None, # ID if scope is not global - Moved later
    timeframe_weeks: int = 4 # Default simulation timeframe 
) -> Dict[str, Any]:
    """Simulates the impact and feasibility of changing a utilization target.

    Args:
        target_scope: The scope of the target change ("global", "team", "resource", "project").
        current_target_utilization: The current utilization target percentage.
        new_target_utilization: The proposed new utilization target percentage.
        scope_id: Identifier for the scope (e.g., team name, resource ID) if not global.
        timeframe_weeks: The duration over which to assess the impact.

    Returns:
        A dictionary containing the simulation results and feasibility analysis.
    """
    scope_desc = f"{target_scope} {scope_id}" if scope_id else "global"
    logger.info(f"Running simulation: Adjusting target utilization for {scope_desc} "
                f"from {current_target_utilization:.1f}% to {new_target_utilization:.1f}% over {timeframe_weeks} weeks.")

    # --- Validate Inputs ---
    if not 0 <= current_target_utilization <= 100 or not 0 <= new_target_utilization <= 100:
        logger.error(f"Invalid target utilization values: Current {current_target_utilization}, New {new_target_utilization}")
        return {"status": "error", "message": "Target utilization must be between 0 and 100."}
    if target_scope not in ["global", "team", "resource", "project"]:
        logger.error(f"Invalid target_scope: {target_scope}")
        return {"status": "error", "message": "Invalid target scope specified."}
    if target_scope != "global" and not scope_id:
         logger.error(f"scope_id is required for target_scope: {target_scope}")
         return {"status": "error", "message": f"Scope ID is required for target scope '{target_scope}'."}

    # --- Simulate Data Fetching (Replace with actual data access) ---
    # Fetch average current ACTUAL utilization and capacity for the scope
    # These are dummy values for demonstration
    current_actual_utilization = 78.0 # Example actual utilization for the scope
    avg_capacity_per_week = 40.0      # Example average weekly capacity per resource in scope
    num_resources_in_scope = 10       # Example number of resources
    
    logger.info(f"Baseline for {scope_desc}: Actual Util={current_actual_utilization:.1f}%, Avg Capacity={avg_capacity_per_week:.1f} hrs/wk")

    # --- Perform Simulation Calculation ---
    # Calculate the required utilization change
    required_utilization_change = new_target_utilization - current_actual_utilization
    
    # Calculate the required change in allocated hours per resource per week
    required_hours_change_per_resource = (required_utilization_change / 100.0) * avg_capacity_per_week
    
    # Assess Feasibility
    current_allocated_hours_per_resource = (current_actual_utilization / 100.0) * avg_capacity_per_week
    simulated_allocated_hours_per_resource = current_allocated_hours_per_resource + required_hours_change_per_resource
    
    feasibility = "Feasible"
    feasibility_notes = []
    if simulated_allocated_hours_per_resource > avg_capacity_per_week:
        feasibility = "Challenging (Exceeds Capacity)"
        over_capacity_hours = simulated_allocated_hours_per_resource - avg_capacity_per_week
        feasibility_notes.append(f"Requires average allocation of {simulated_allocated_hours_per_resource:.1f} hrs/wk, exceeding average capacity by {over_capacity_hours:.1f} hrs/wk.")
        feasibility_notes.append("May require overtime, scope reduction elsewhere, or is potentially unachievable.")
    elif simulated_allocated_hours_per_resource < 0:
         feasibility = "Unrealistic (Negative Allocation)"
         feasibility_notes.append(f"Implies a negative allocation of {simulated_allocated_hours_per_resource:.1f} hrs/wk.")
    elif required_hours_change_per_resource > 0:
        feasibility = "Feasible (Requires Action)"
        feasibility_notes.append(f"Requires an average increase of {required_hours_change_per_resource:.1f} allocated hrs/wk per resource.")
        feasibility_notes.append("Additional billable work or internal projects may be needed.")
    elif required_hours_change_per_resource < 0:
         feasibility = "Feasible (Reduces Load)"
         feasibility_notes.append(f"Allows for an average decrease of {abs(required_hours_change_per_resource):.1f} allocated hrs/wk per resource.")
         feasibility_notes.append("May increase availability for training or reduce pressure.")
    else:
        feasibility_notes.append("No change required based on current actual utilization.")

    # --- Prepare Results ---
    results = {
        "status": "success",
        "simulation_type": "target_adjustment",
        "parameters": {
            "target_scope": target_scope,
            "scope_id": scope_id,
            "current_target_utilization": current_target_utilization,
            "new_target_utilization": new_target_utilization,
            "timeframe_weeks": timeframe_weeks
        },
        "baseline_state": {
            "current_actual_utilization_percent": round(current_actual_utilization, 2),
            "current_target_utilization_percent": round(current_target_utilization, 2),
            "avg_allocated_hours_per_resource_per_week": round(current_allocated_hours_per_resource, 2)
        },
        "simulated_impact_analysis": {
            "baseline_actual_utilization_percent": round(current_actual_utilization, 2),
            "new_target_utilization_percent": round(new_target_utilization, 2),
            "required_utilization_change_percent": round(required_utilization_change, 2),
            "required_hours_change_per_resource_per_week": round(required_hours_change_per_resource, 2),
            "simulated_allocated_hours_per_resource_per_week": round(simulated_allocated_hours_per_resource, 2),
            "feasibility": feasibility,
            "feasibility_notes": feasibility_notes
        },
        "summary": f"Adjusting target utilization for {scope_desc} from {current_target_utilization:.1f}% to {new_target_utilization:.1f}%. Feasibility: {feasibility}. Requires an average change of {required_hours_change_per_resource:.1f} allocated hrs/wk per resource."
    }

    logger.info(f"Simulation complete for target adjustment for {scope_desc}. Feasibility: {feasibility}")
    return results

def calculate_projected_outcomes(simulation_result: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder: Calculates broader projected outcomes based on simulation results.
    
    Currently, this function only acknowledges the input simulation results
    and indicates that detailed outcome projection (e.g., cost impact) is pending.
    
    Args:
        simulation_result: The dictionary returned by a simulation function like 
                           simulate_resource_change or simulate_target_adjustment.
                           
    Returns:
        A dictionary indicating the status.
    """
    logger.warning("calculate_projected_outcomes called, but detailed projection (e.g., cost) is not implemented yet.")
    
    if not isinstance(simulation_result, dict) or 'status' not in simulation_result:
        logger.error("Invalid input provided to calculate_projected_outcomes.")
        return {"status": "error", "message": "Invalid simulation result input."}
        
    if simulation_result.get("status") != "success":
        logger.info("calculate_projected_outcomes skipped as input simulation was not successful.")
        return {"status": "skipped", "message": "Input simulation did not succeed.", "original_result": simulation_result}
        
    # In the future, this function would analyze simulation_result 
    # and potentially query cost data, project plans, etc., to calculate broader impacts.
    
    return {
        "status": "pending_implementation", 
        "message": "Detailed outcome projection (e.g., cost, timeline impact) is not yet implemented.",
        "simulation_summary": simulation_result.get("summary", "No summary provided.") # Pass through summary
    }

# Example usage (for testing purposes)
if __name__ == '__main__':
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # NOTE: Replace with actual LLM config loading (e.g., from environment variables)
    config_list = autogen.config_list_from_json("OAI_CONFIG_LIST")
    llm_config = {"config_list": config_list, "timeout": 60}

    simulation_agent = SimulationAgent(llm_config=llm_config)
    
    logger.info(f"Agent Name: {simulation_agent.name}")
    logger.info(f"System Message: \n{simulation_agent.system_message}")
    
    # Test placeholder functions (they will just log warnings)
    simulate_resource_change()
    simulate_target_adjustment()
    calculate_projected_outcomes()

    print("\nResult 3 (No change case):", json.dumps(result3, indent=2))

    # --- Test simulate_target_adjustment ---
    print("\n--- Testing simulate_target_adjustment ---")
    test_target_params = {
        "target_scope": "team",
        "scope_id": "DataScience",
        "current_target_utilization": 80.0,
        "new_target_utilization": 85.0
    }
    result_target = simulate_target_adjustment(**test_target_params)
    print("Target Result:", json.dumps(result_target, indent=2))
    
    # Test calculate_projected_outcomes with a successful simulation result
    print("\n--- Testing calculate_projected_outcomes (Placeholder) ---")
    result_projection = calculate_projected_outcomes(result1) # Use result from first resource change test
    print("Projection Result:", json.dumps(result_projection, indent=2))
    
    # Test calculate_projected_outcomes with a failed simulation result
    result_projection_fail = calculate_projected_outcomes(result2) # Use result from failed resource change test
    print("Projection Result (Fail Input):", json.dumps(result_projection_fail, indent=2)) 