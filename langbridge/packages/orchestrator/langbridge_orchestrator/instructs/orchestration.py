class OrchestrationInstruct: 
    def __init__(
        self,
        agent_id: str,
        agent_instruct: str,
        orchestration_id: str,
        
        orchestration_gbl_instruct: str = "",
        orchestration_response_instruct: str = "",
    ):
        self.agent_id = agent_id
        self.agent_instruct = agent_instruct
        self.orchestration_id = orchestration_id
        self.orchestration_gbl_instruct = orchestration_gbl_instruct
        self.orchestration_response_instruct = orchestration_response_instruct
        
        
    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "agent_instruct": self.agent_instruct,
            "orchestration_id": self.orchestration_id,
            "orchestration_gbl_instruct": self.orchestration_gbl_instruct,
            "orchestration_response_instruct": self.orchestration_response_instruct,
        }