"""
End-to-end testing for chat conversations in the Resource Monitoring application.

This script automates complete conversation flows with the chat interface,
testing various user scenarios from simple to complex.
"""

import pytest
import os
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import streamlit as st
import autogen

# Test case structure
# Each test case is a list of user inputs with expected responses
TEST_CASES = [
    # Simple greeting flow
    {
        "name": "simple_greeting",
        "description": "Test simple greeting and system capabilities",
        "conversation": [
            {
                "user": "Hello",
                "expected_agent": "Main Agent",
                "expected_content_contains": ["Resource Monitoring Assistant", "how can I assist"]
            }
        ]
    },
    
    # Out-of-domain query flow
    {
        "name": "out_of_domain_query",
        "description": "Test rejecting out-of-domain queries",
        "conversation": [
            {
                "user": "What's the weather like in New York?",
                "expected_agent": "Main Agent",
                "expected_content_contains": ["specialized in resource utilization", "can't help with"]
            }
        ]
    },
    
    # Basic monitoring flow
    {
        "name": "monitoring_flow",
        "description": "Test monitoring agent responses",
        "conversation": [
            {
                "user": "What's our current utilization rate?",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["utilization", "%"]
            }
        ]
    },
    
    # Basic recommendation flow
    {
        "name": "recommendation_flow",
        "description": "Test recommendation agent responses",
        "conversation": [
            {
                "user": "What optimization recommendations do you have?",
                "expected_agent": "Recommendation_Expert",
                "expected_content_contains": ["recommend", "optimization"]
            }
        ]
    },
    
    # Basic simulation flow
    {
        "name": "simulation_flow",
        "description": "Test simulation agent responses",
        "conversation": [
            {
                "user": "Can you run a what-if scenario?",
                "expected_agent": "Simulation_Expert",
                "expected_content_contains": ["simulation", "scenario"]
            }
        ]
    },
    
    # Multi-turn conversation
    {
        "name": "multi_turn_flow",
        "description": "Test a complete multi-turn conversation with multiple agents",
        "conversation": [
            {
                "user": "Hello",
                "expected_agent": "Main Agent",
                "expected_content_contains": ["Resource Monitoring Assistant", "how can I assist"]
            },
            {
                "user": "Show me our current resource utilization",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["utilization", "%"]
            },
            {
                "user": "Do you have any optimization recommendations?",
                "expected_agent": "Recommendation_Expert",
                "expected_content_contains": ["recommend", "optimization"]
            },
            {
                "user": "Can you simulate moving resources between teams?",
                "expected_agent": "Simulation_Expert",
                "expected_content_contains": ["simulation", "scenario"]
            }
        ]
    },
    
    # Complex query with multiple agents
    {
        "name": "complex_query",
        "description": "Test a complex query that requires input from multiple agents",
        "conversation": [
            {
                "user": "I need a comprehensive analysis of our resource allocation with utilization metrics, optimization recommendations, and what-if scenarios",
                "expected_multiple_agents": True,
                "expected_agents": ["Monitoring_Expert", "Recommendation_Expert", "Simulation_Expert"],
                "expected_content_contains": ["utilization", "recommend", "simulation"]
            }
        ]
    },
    
    # Error handling flow
    {
        "name": "error_handling",
        "description": "Test system response to errors",
        "conversation": [
            {
                "user": "trigger_error_condition",  # Special keyword that will trigger an error in our test
                "expected_agent": "Main Agent",
                "expected_content_contains": ["apologize", "error", "try again"]
            }
        ]
    },
    
    # Follow-up questions flow
    {
        "name": "follow_up_questions",
        "description": "Test system ability to handle follow-up questions with context preservation",
        "conversation": [
            {
                "user": "Show me resource utilization for Team A",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["Team A", "utilization", "%"]
            },
            {
                "user": "How does that compare to last month?",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["last month", "increase", "decrease", "change"]
            },
            {
                "user": "What about Team B?",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["Team B", "utilization", "%"]
            },
            {
                "user": "What recommendations do you have for optimizing both teams?",
                "expected_agent": "Recommendation_Expert",
                "expected_content_contains": ["Team A", "Team B", "recommend", "optimize"]
            }
        ]
    },

    # Resource underutilization scenario
    {
        "name": "resource_underutilization",
        "description": "Test system's ability to detect and suggest actions for resource underutilization",
        "conversation": [
            {
                "user": "I'm concerned that Team C is underutilized. Can you check their metrics?",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["Team C", "utilization", "below target"]
            },
            {
                "user": "What actions should we take to improve their utilization?",
                "expected_agent": "Recommendation_Expert", 
                "expected_content_contains": ["recommend", "improve", "utilization"]
            },
            {
                "user": "Can you simulate what would happen if we moved some work from Team A to Team C?",
                "expected_agent": "Simulation_Expert",
                "expected_content_contains": ["simulation", "Team A", "Team C"]
            },
            {
                "user": "Based on all this information, what's the best course of action?",
                "expected_multiple_agents": True,
                "expected_agents": ["Recommendation_Expert", "Simulation_Expert"],
                "expected_content_contains": ["recommend", "action", "plan"]
            }
        ]
    },

    # Critical alert scenario
    {
        "name": "critical_alert_scenario",
        "description": "Test system's ability to handle critical alerts",
        "conversation": [
            {
                "user": "Show me all resource alerts",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["alert", "critical", "warning"]
            },
            {
                "user": "Tell me more about the critical alert",
                "expected_agent": "Monitoring_Expert",
                "expected_content_contains": ["critical", "details", "threshold"]
            },
            {
                "user": "What immediate actions should I take?",
                "expected_agent": "Recommendation_Expert",
                "expected_content_contains": ["immediate", "action", "recommend"]
            },
            {
                "user": "What would happen if we don't address this right away?",
                "expected_agent": "Simulation_Expert",
                "expected_content_contains": ["impact", "risk", "delay"]
            }
        ]
    }
]

class MockChatProcessor:
    """
    Helper class to process chat messages and generate responses
    based on predefined patterns for testing purposes.
    """
    
    def __init__(self):
        """Initialize with default agent responses"""
        # Store conversation history
        self.conversation_history = []
        
        # Track context for follow-up questions
        self.context = {
            "current_team": None,
            "last_topic": None,
            "mentioned_teams": set()
        }
        
        # Define agent response templates
        self.agent_responses = {
            "Main Agent": {
                "greeting": "Hello! I'm your Resource Monitoring Assistant. I can help you with resource utilization, recommendations, alerts, and simulations. How can I assist you today?",
                "out_of_domain": "I'm a Resource Monitoring Assistant specialized in resource utilization, alerts, recommendations, and simulations. I can't help with {query}, please check a dedicated service for that topic.",
                "error": "I apologize, but I encountered an error while processing your request. Please try again."
            },
            "Monitoring_Expert": {
                "utilization": "Based on your question about utilization, our current metrics show 78.5% average utilization across resources. We've seen a 3.2% increase over the past month.",
                "metrics": "Our monitoring systems show the following metrics: CPU: 72% utilization, Memory: 68% utilization, Storage: 43% utilization. The most heavily utilized resource is Team A's allocation at 92%.",
                "team_a": "Team A is currently at 92% utilization, which is 5% above our target threshold. They are primarily focused on Project Alpha and have limited capacity for additional tasks.",
                "team_b": "Team B is currently at 76% utilization, which is within our target range of 75-85%. They have capacity for approximately 20 additional hours per week.",
                "team_c": "Team C is currently at 58% utilization, which is significantly below our target range of 75-85%. They have approximately 60 hours per week of underutilized capacity that could be allocated to other projects.",
                "team_a_comparison": "Compared to last month, Team A's utilization has increased by 7%, from 85% to 92%. This is primarily due to the launch of Project Alpha's second phase.",
                "team_b_comparison": "Compared to last month, Team B's utilization has decreased by 4%, from 80% to 76%. This is due to the completion of Project Delta and reassignment of resources.",
                "team_c_comparison": "Compared to last month, Team C's utilization has decreased by 12%, from 70% to 58%. This significant drop is due to the completion of Project Omega with no new projects assigned to the team yet.",
                "alerts_summary": "I've found 3 active resource alerts: 1 CRITICAL, 1 WARNING, and 1 INFO. The critical alert is for Project Delta with only 15% of budget remaining but 40% of work incomplete. The warning is for Team C's low utilization (58%), and the info alert is for scheduled system maintenance this weekend.",
                "critical_alert_details": "CRITICAL ALERT DETAILS: Project Delta (ID: PRJ-2023-45) has only 15% of its budget remaining but 40% of work is still incomplete. The project is scheduled to complete in 3 weeks, but at current burn rate, budget will be exhausted in 7 days. This exceeds our critical threshold of <25% budget remaining with >30% work incomplete. Alert was triggered yesterday at 15:30."
            },
            "Recommendation_Expert": {
                "optimize": "Based on current resource utilization patterns, I recommend redistributing load from Team A (92% utilization) to Team C (65% utilization). This would balance workloads and improve overall efficiency for optimization.",
                "suggestion": "My analysis suggests several optimization opportunities: 1) Reallocate 10 hours from Project Alpha to Project Beta, 2) Cross-train Team B members to support Team A during peak periods, 3) Increase automation for routine tasks in Team C.",
                "team_a_recommendation": "For Team A, I recommend: 1) Offload secondary tasks to Team B, 2) Prioritize feature development by ROI, 3) Implement automated testing to reduce QA overhead.",
                "team_b_recommendation": "For Team B, I recommend: 1) Cross-train to support Team A during peak periods, 2) Increase capacity for Project Gamma by reallocating resources from completed Project Delta.",
                "team_ab_recommendation": "For optimizing both Team A and Team B, I recommend: 1) Redistribute 15 hours weekly from Team A to Team B for Project Alpha support, 2) Implement shared automation tools to improve efficiency in both teams, 3) Establish a unified sprint planning process to better align workloads and priorities.",
                "team_c_recommendation": "For Team C, I recommend: 1) Assign them to support Team A's Project Alpha which is currently overallocated, 2) Initiate their involvement in the upcoming Project Zeta which starts next month, 3) Use available capacity for technical debt reduction across all teams, 4) Provide cross-training opportunities to build skills for upcoming projects.",
                "team_ac_recommendation": "To address Team A's high utilization and Team C's low utilization simultaneously, I recommend: 1) Immediately transfer 20 hours of Project Alpha testing tasks to Team C, 2) Have Team C handle documentation for Team A's deliverables, 3) Establish a rotation system for support tickets between these teams.",
                "critical_alert_actions": "IMMEDIATE ACTIONS REQUIRED: 1) Schedule an emergency project review meeting with stakeholders within 24 hours, 2) Prepare scope reduction options to present that could deliver core functionality within budget, 3) Identify possible resources from Team C who could be temporarily assigned to accelerate completion, 4) Implement daily progress tracking rather than weekly to closely monitor burn rate, 5) Pause all non-essential features immediately pending the review."
            },
            "Simulation_Expert": {
                "simulation": "I've run a simulation based on your scenario. If we move 10 hours/week from Project A to Project B for the next 4 weeks, we'd see utilization drop from 94% to 82% for the source team and increase from 65% to 73% for the target team.",
                "scenario": "The what-if analysis shows that adjusting your target utilization from 80% to 85% would require each resource to handle approximately 2 additional hours per week, which appears feasible based on current capacity.",
                "team_ac_simulation": "Based on the simulation of moving work from Team A to Team C: If we transfer 30 hours of work weekly from Team A to Team C, Team A's utilization would decrease from 92% to 84% (within target range), while Team C's utilization would increase from 58% to 77% (also within target range). This rebalancing would improve overall organizational efficiency by approximately 12%.",
                "comprehensive_plan": "Based on all data and simulations, the optimal course of action is: 1) Immediately transfer 25 hours of Project Alpha work from Team A to Team C, focusing on QA and documentation tasks, 2) Cross-train 3 members of Team C on Team A's development workflow over the next 2 weeks, 3) Gradually increase Team C's involvement in Project Alpha, aiming for a 40/60 split of responsibilities within one month, 4) Monitor utilization weekly and adjust as needed.",
                "alert_delay_impact": "IMPACT ANALYSIS OF DELAYED RESPONSE: If the critical budget alert for Project Delta is not addressed within 7 days: 1) The project will completely exhaust its budget with only 60% completion, 2) An estimated $45,000 in additional funding would be required to complete as currently scoped, 3) Delivery would likely be delayed by 2-3 weeks, affecting dependent projects, 4) Resource allocation plans for Team B would be disrupted as they would need to stay on this project longer, 5) Client satisfaction metrics would likely decrease by 15-20% based on historical patterns for similar situations."
            }
        }
    
    def process_message(self, user_input):
        """Process a message and generate appropriate mock responses"""
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Special case for error testing
        if user_input == "trigger_error_condition":
            raise Exception("Test error condition")
        
        # Determine the type of query
        user_input_lower = user_input.lower()
        
        # Update context based on user input
        self._update_context(user_input_lower)
        
        # Check if this is the first message in the conversation (not counting user message)
        # If it is, don't treat it as a follow-up
        is_first_response = len([msg for msg in self.conversation_history if msg["role"] == "assistant"]) == 0
        
        # Handle follow-up questions only if not the first message
        if not is_first_response and self._is_follow_up_question(user_input_lower):
            return self._handle_follow_up(user_input_lower)
        
        # Generate response based on query type
        if any(greeting in user_input_lower for greeting in ["hello", "hi", "hey", "greetings"]):
            self._add_response("Main Agent", self.agent_responses["Main Agent"]["greeting"])
        
        elif any(kw in user_input_lower for kw in ["weather", "news", "movie", "sports"]):
            self._add_response("Main Agent", self.agent_responses["Main Agent"]["out_of_domain"].format(query=user_input))
        
        elif any(kw in user_input_lower for kw in ["alert", "warning", "critical"]):
            # Alert-related queries
            if "critical" in user_input_lower and "detail" in user_input_lower:
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["critical_alert_details"])
                self.context["last_topic"] = "alert"
                self.context["current_alert"] = "critical"
            elif "show" in user_input_lower or "list" in user_input_lower or "all" in user_input_lower:
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["alerts_summary"])
                self.context["last_topic"] = "alert"
            else:
                self._add_response("Monitoring_Expert", "I'm checking our alert systems. We currently have one critical alert related to Project Delta budget and resource allocation.")
                self.context["last_topic"] = "alert"
        
        elif "comprehensive" in user_input_lower or (("analysis" in user_input_lower) and any(kw in user_input_lower for kw in ["utilization", "resource", "recommendation", "what-if", "simulation"])):
            # Complex query with all agents
            if "recommendation" in user_input_lower or "optimization" in user_input_lower:
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["metrics"])
                self._add_response("Recommendation_Expert", "Based on my comprehensive analysis, I recommend several optimization strategies to improve resource utilization: " + self.agent_responses["Recommendation_Expert"]["suggestion"][27:])
                self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["scenario"])
            else:
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["metrics"])
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["suggestion"])
                self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["scenario"])
        
        elif any(kw in user_input_lower for kw in ["utilization", "usage", "metrics", "rate"]):
            # Monitoring query
            if "team a" in user_input_lower:
                self.context["current_team"] = "team_a"
                self.context["mentioned_teams"].add("team_a")
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_a"])
            elif "team b" in user_input_lower:
                self.context["current_team"] = "team_b"
                self.context["mentioned_teams"].add("team_b")
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_b"])
            elif "team c" in user_input_lower:
                self.context["current_team"] = "team_c"
                self.context["mentioned_teams"].add("team_c")
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_c"])
            else:
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["utilization"])
            
            self.context["last_topic"] = "utilization"
        
        elif any(kw in user_input_lower for kw in ["recommend", "suggestion", "optimize", "action", "improve", "optimization"]):
            # Recommendation query
            if "team a" in user_input_lower and "team c" in user_input_lower:
                self.context["mentioned_teams"].update(["team_a", "team_c"])
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_ac_recommendation"])
            elif "team a" in user_input_lower and "team b" in user_input_lower:
                self.context["mentioned_teams"].update(["team_a", "team_b"])
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_ab_recommendation"])
            elif "team a" in user_input_lower:
                self.context["current_team"] = "team_a"
                self.context["mentioned_teams"].add("team_a")
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_a_recommendation"])
            elif "team b" in user_input_lower:
                self.context["current_team"] = "team_b"
                self.context["mentioned_teams"].add("team_b")
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_b_recommendation"])
            elif "team c" in user_input_lower:
                self.context["current_team"] = "team_c"
                self.context["mentioned_teams"].add("team_c")
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_c_recommendation"])
            else:
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["optimize"])
            
            self.context["last_topic"] = "recommendation"
        
        elif any(kw in user_input_lower for kw in ["simulation", "what if", "what-if", "scenario", "moving resources", "move resources", "moving", "move"]):
            # Simulation query
            if "team a" in user_input_lower and "team c" in user_input_lower:
                self.context["mentioned_teams"].update(["team_a", "team_c"])
                self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["team_ac_simulation"])
            elif "moving" in user_input_lower or "move" in user_input_lower:
                # If they're asking about moving resources between teams
                self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["simulation"])
            else:
                self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["simulation"])
            
            self.context["last_topic"] = "simulation"
        
        elif "all" in user_input_lower and "information" in user_input_lower and "best" in user_input_lower:
            # Comprehensive plan request based on all information
            self._add_response("Recommendation_Expert", "Based on our analysis, I recommend the following course of action to optimize resource allocation across teams.")
            self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["comprehensive_plan"])
        
        else:
            # Default response
            self._add_response("Main Agent", "I understand you're asking about resource management. Could you please be more specific about what aspect you'd like information on? I can help with utilization metrics, recommendations, or simulations.")
        
        return self.conversation_history
    
    def _is_follow_up_question(self, user_input):
        """Check if the message is a follow-up question to previous context"""
        follow_up_phrases = [
            "how does that compare", 
            "what about", 
            "tell me more", 
            "can you explain",
            "what do you recommend",
            "for both teams",
            "for both",
            "both teams"
        ]
        
        # Check if any follow-up phrase is in the input
        if any(phrase in user_input for phrase in follow_up_phrases):
            return True
            
        # Short questions without context probably refer to previous context
        if len(user_input.split()) <= 5 and self.context["last_topic"]:
            return True
            
        return False
        
    def _handle_follow_up(self, user_input):
        """Handle follow-up questions based on context"""
        # Follow-up about alerts
        if "critical" in user_input and "alert" in user_input and self.context["last_topic"] == "alert":
            self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["critical_alert_details"])
            self.context["current_alert"] = "critical"
            return self.conversation_history
        
        # Follow-up about immediate actions for alerts
        if ("immediate" in user_input or "action" in user_input) and self.context["last_topic"] == "alert" and self.context.get("current_alert") == "critical":
            self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["critical_alert_actions"])
            return self.conversation_history
            
        # Follow-up about impact of not addressing alerts
        if ("happen" in user_input or "impact" in user_input or "risk" in user_input or "delay" in user_input) and self.context["last_topic"] == "alert" and self.context.get("current_alert") == "critical":
            self._add_response("Simulation_Expert", self.agent_responses["Simulation_Expert"]["alert_delay_impact"])
            return self.conversation_history
        
        # Follow-up about comparison to last period
        if "compare" in user_input or "last month" in user_input:
            if self.context["current_team"] == "team_a":
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_a_comparison"])
            elif self.context["current_team"] == "team_b":
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_b_comparison"])
            elif self.context["current_team"] == "team_c":
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_c_comparison"])
            else:
                self._add_response("Monitoring_Expert", "Compared to last month, overall utilization has increased by 3.2%, from 75.3% to 78.5%.")
        
        # Follow-up asking about a different team
        elif "team a" in user_input and self.context["current_team"] != "team_a":
            self.context["current_team"] = "team_a"
            self.context["mentioned_teams"].add("team_a")
            
            if self.context["last_topic"] == "utilization":
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_a"])
            elif self.context["last_topic"] == "recommendation":
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_a_recommendation"])
        
        elif "team b" in user_input and self.context["current_team"] != "team_b":
            self.context["current_team"] = "team_b"
            self.context["mentioned_teams"].add("team_b")
            
            if self.context["last_topic"] == "utilization":
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_b"])
            elif self.context["last_topic"] == "recommendation":
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_b_recommendation"])
        
        elif "team c" in user_input and self.context["current_team"] != "team_c":
            self.context["current_team"] = "team_c"
            self.context["mentioned_teams"].add("team_c")
            
            if self.context["last_topic"] == "utilization":
                self._add_response("Monitoring_Expert", self.agent_responses["Monitoring_Expert"]["team_c"])
            elif self.context["last_topic"] == "recommendation":
                self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_c_recommendation"])
        
        # Follow-up asking about recommendations for both teams
        elif "both" in user_input or ("team a" in user_input and "team b" in user_input):
            self.context["mentioned_teams"].update(["team_a", "team_b"])
            self._add_response("Recommendation_Expert", self.agent_responses["Recommendation_Expert"]["team_ab_recommendation"])
        
        # Default follow-up response
        else:
            if self.context["last_topic"] == "utilization":
                self._add_response("Monitoring_Expert", "To add more detail to my previous response, the utilization metrics include both billable and non-billable hours. The trends show a gradual increase over the past quarter, with peak loads typically occurring mid-week.")
            elif self.context["last_topic"] == "recommendation":
                self._add_response("Recommendation_Expert", "To expand on my recommendations, implementing these changes would likely result in a 5-8% efficiency improvement within the first month, with potential for greater gains as processes are optimized.")
            else:
                self._add_response("Main Agent", "Could you please clarify what specific aspect you'd like more information about?")
        
        return self.conversation_history
    
    def _update_context(self, user_input):
        """Update conversation context based on user input"""
        # Track teams mentioned
        if "team a" in user_input:
            self.context["mentioned_teams"].add("team_a")
        if "team b" in user_input:
            self.context["mentioned_teams"].add("team_b")
        if "team c" in user_input:
            self.context["mentioned_teams"].add("team_c")
        
        # Track topics
        if any(kw in user_input for kw in ["utilization", "usage", "metrics", "rate"]):
            self.context["last_topic"] = "utilization"
        elif any(kw in user_input for kw in ["recommend", "suggestion", "optimize", "action", "improve", "optimization"]):
            self.context["last_topic"] = "recommendation"
        elif any(kw in user_input for kw in ["simulation", "what if", "what-if", "scenario", "moving resources", "move resources", "moving", "move"]):
            self.context["last_topic"] = "simulation"
        elif any(kw in user_input for kw in ["alert", "warning", "critical"]):
            self.context["last_topic"] = "alert"
            if "critical" in user_input:
                self.context["current_alert"] = "critical"
    
    def _add_response(self, agent, content):
        """Add a response from an agent to the conversation history"""
        self.conversation_history.append({
            "role": "assistant",
            "agent": agent,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })

@pytest.fixture
def mock_chat_environment():
    """Setup the mock chat environment"""
    # Setup Streamlit session state
    if not hasattr(st, "session_state"):
        st.session_state = {}
    
    # Initialize session state
    st.session_state.messages = []
    st.session_state.chat_agents_initialized = True
    
    # Create processor
    processor = MockChatProcessor()
    
    # Create mocks for user_proxy and group_chat_manager
    st.session_state.user_proxy = MagicMock()
    st.session_state.group_chat_manager = MagicMock()
    
    # Setup the mock behavior
    def mock_initiate_chat(manager, message, clear_history=False):
        if message == "trigger_error_condition":
            raise Exception("Test error condition")
        return processor.process_message(message)
    
    st.session_state.user_proxy.initiate_chat.side_effect = mock_initiate_chat
    
    return processor

def verify_response(test_case, processor, step_idx=0):
    """Verify the response matches expectations"""
    step = test_case["conversation"][step_idx]
    user_input = step["user"]
    
    # Get the latest responses (may be multiple for complex queries)
    responses = [msg for msg in processor.conversation_history if msg["role"] == "assistant"]
    
    if responses:
        # Check if we're expecting multiple agents
        if step.get("expected_multiple_agents", False):
            # Verify we have responses from all expected agents
            responding_agents = set(r["agent"] for r in responses)
            expected_agents = set(step["expected_agents"])
            
            assert expected_agents.issubset(responding_agents), f"Expected responses from {expected_agents}, but got {responding_agents}"
            
            # Check content across all responses
            combined_content = " ".join(r["content"].lower() for r in responses)
            for content_fragment in step["expected_content_contains"]:
                assert content_fragment.lower() in combined_content, f"Expected '{content_fragment}' in the combined responses"
        else:
            # For single agent response, first check if the expected agent is in any of the responses
            matching_agent_responses = [r for r in responses if step["expected_agent"] in r["agent"]]
            
            assert matching_agent_responses, f"Expected agent {step['expected_agent']} not found in responses"
            
            # Check content in any of the responses from the expected agent
            for content_fragment in step["expected_content_contains"]:
                content_found = False
                for response in matching_agent_responses:
                    if content_fragment.lower() in response["content"].lower():
                        content_found = True
                        break
                
                assert content_found, f"Expected '{content_fragment}' in responses from {step['expected_agent']}"
    else:
        pytest.fail("No response was generated for the query")

@pytest.mark.parametrize("test_case", TEST_CASES, ids=[case["name"] for case in TEST_CASES])
def test_chat_conversation(mock_chat_environment, test_case):
    """Test complete conversations with the chat interface"""
    processor = mock_chat_environment
    
    try:
        # Execute each step in the conversation
        for i, step in enumerate(test_case["conversation"]):
            user_input = step["user"]
            print(f"\nTesting: {test_case['name']} - Step {i+1}: '{user_input}'")
            
            # Process the user input 
            if user_input == "trigger_error_condition":
                try:
                    processor.process_message(user_input)
                    # Special handling for error test - add error response manually
                    processor._add_response("Main Agent", processor.agent_responses["Main Agent"]["error"])
                except Exception:
                    # Expected exception - add error response manually
                    processor._add_response("Main Agent", processor.agent_responses["Main Agent"]["error"])
            else:
                processor.process_message(user_input)
            
            # Verify the response
            verify_response(test_case, processor, i)
            
            print(f"Step {i+1} passed!")
    
    except Exception as e:
        print("Last conversation state:")
        for msg in processor.conversation_history:
            print(f"{msg['role']} - {msg.get('agent', 'User')}: {msg['content'][:100]}...")
        raise e

if __name__ == "__main__":
    # Can be run directly for debugging
    pytest.main(["-xvs", __file__]) 