# Intuno SDK Enhancement Plan - Federation of Agents Patterns

## Executive Summary

This document outlines the enhancements needed for the Intuno SDK to support the Federation of Agents design patterns. The SDK must evolve to expose new features like semantic ranking, trust scores, orchestration, and enhanced discovery while maintaining backward compatibility.

---

## Current SDK State

### ✅ What's Already Implemented
- **Basic discovery**: `client.discover(query, limit)` - uses GET endpoint
- **Agent invocation**: `client.invoke()` and `agent.invoke()` / `agent.ainvoke()`
- **Model classes**: `Agent`, `Capability`, `InvokeResult`
- **LangChain integration**: `create_discovery_tool()`, `make_tools_from_agent()`
- **OpenAI integration**: `get_discovery_tool_openai_schema()`, `make_openai_tools_from_agent()`
- **Sync & Async clients**: `IntunoClient` and `AsyncIntunoClient`

### ❌ What's Missing
- Enhanced discover with filters and ranking
- Trust scores and metrics access
- Orchestration/DAG support
- Async invocation support (job-based)
- Metadata exposure (cost, latency hints)
- VCV version information

---

## Enhancement Plan by Pattern

### Pattern 1: Capability Embeddings (VCVs)

#### Changes Needed

**1. Update Models** (Priority: High)
- [ ] Add `vcv_version` field to `Agent` model
- [ ] Add `vcv_version` field to `Capability` model
- [ ] Optionally expose `capability_vector` in detailed responses (if API provides it)

**2. Add Refresh Method** (Priority: Medium)
- [ ] `client.refresh_agent_vcv(agent_uuid)` - calls `POST /registry/agents/{uuid}/refresh-vcv`
- [ ] Async version: `await client.arefresh_agent_vcv(agent_uuid)`

**Implementation:**
```python
# In IntunoClient
def refresh_agent_vcv(self, agent_uuid: str) -> bool:
    """Refresh embeddings for an agent and its capabilities."""
    response = self._http_client.post(
        f"/registry/agents/{agent_uuid}/refresh-vcv"
    )
    response.raise_for_status()
    return True

# In AsyncIntunoClient
async def arefresh_agent_vcv(self, agent_uuid: str) -> bool:
    """Asynchronously refresh embeddings for an agent."""
    response = await self._http_client.post(
        f"/registry/agents/{agent_uuid}/refresh-vcv"
    )
    response.raise_for_status()
    return True
```

---

### Pattern 2: Semantic Routing & Ranking

#### Changes Needed

**1. Enhanced Discover Method** (Priority: Critical ⭐)
- [ ] Update `discover()` to support new `POST /registry/discover` endpoint
- [ ] Add `DiscoverOptions` class for filters and ranking options
- [ ] Return ranked results with scores
- [ ] Maintain backward compatibility with old GET endpoint

**2. New Models**
- [ ] `DiscoverOptions` - filters, max_results, ranking weights
- [ ] `RankedAgent` - extends `Agent` with score, estimated_latency, estimated_cost
- [ ] `CapabilityMetadata` - cost, latency hints

**Implementation:**
```python
from typing import Optional
from pydantic import BaseModel, Field

class CapabilityMetadata(BaseModel):
    """Metadata for a capability (cost, latency hints)."""
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    visibility: str = "public"

class DiscoverOptions(BaseModel):
    """Options for semantic discovery with ranking."""
    query: str
    max_results: int = Field(default=10, ge=1, le=50)
    filters: Optional["DiscoverFilters"] = None
    ranking_weights: Optional["RankingWeights"] = None

class DiscoverFilters(BaseModel):
    """Filters for discovery."""
    max_cost_usd: Optional[float] = None
    max_latency_ms: Optional[int] = None
    min_trust_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    tags: Optional[list[str]] = None
    capability: Optional[str] = None

class RankingWeights(BaseModel):
    """Custom weights for ranking function."""
    similarity: float = Field(default=0.7, ge=0.0, le=1.0)
    latency: float = Field(default=0.1, ge=0.0, le=1.0)
    cost: float = Field(default=0.1, ge=0.0, le=1.0)
    trust: float = Field(default=0.1, ge=0.0, le=1.0)

class RankedAgent(Agent):
    """Agent with ranking information."""
    score: float = Field(..., ge=0.0, le=1.0)
    estimated_latency_ms: Optional[int] = None
    estimated_cost_usd: Optional[float] = None

# Updated discover method
def discover(
    self,
    query: str,
    limit: int = 10,
    filters: Optional[DiscoverFilters] = None,
    ranking_weights: Optional[RankingWeights] = None,
    use_ranking: bool = True,  # New default
) -> List[RankedAgent]:
    """
    Discover agents using semantic search with optional ranking.
    
    Args:
        query: Natural language description of desired capability
        limit: Maximum number of results (deprecated, use options)
        filters: Optional filters for cost, latency, trust
        ranking_weights: Custom ranking weights
        use_ranking: If True, use POST endpoint with ranking (default: True)
    
    Returns:
        List of RankedAgent objects ordered by score
    """
    if use_ranking:
        # Use new POST endpoint with ranking
        payload = {
            "query": query,
            "max_results": limit,
        }
        if filters:
            payload["filters"] = filters.model_dump(exclude_none=True)
        if ranking_weights:
            payload["ranking_weights"] = ranking_weights.model_dump(exclude_none=True)
        
        response = self._http_client.post("/registry/discover", json=payload)
        response.raise_for_status()
        return [RankedAgent(**agent_data) for agent_data in response.json()]
    else:
        # Fallback to old GET endpoint for backward compatibility
        response = self._http_client.get(
            "/registry/discover", params={"query": query, "limit": limit}
        )
        response.raise_for_status()
        agents = [Agent(**agent_data) for agent_data in response.json()]
        # Convert to RankedAgent with default score
        return [
            RankedAgent(**agent.model_dump(), score=1.0)
            for agent in agents
        ]
```

**3. Update Capability Model**
```python
class Capability(BaseModel):
    """Represents an agent's capability."""
    id: str
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(..., alias="inputSchema")
    output_schema: Dict[str, Any] = Field(..., alias="outputSchema")
    metadata: Optional[CapabilityMetadata] = None  # NEW
    vcv_version: Optional[str] = None  # NEW
```

---

### Pattern 3: Task Decomposition & Orchestration

#### Changes Needed

**1. Orchestration Models** (Priority: Medium)
- [ ] `Orchestration` model
- [ ] `DAGNode` and `DAGEdge` models
- [ ] `OrchestrationStatus` enum
- [ ] `OrchestrationResult` model

**2. Orchestration Methods**
- [ ] `client.create_orchestration()` - create and execute DAG
- [ ] `client.get_orchestration_status()` - poll status
- [ ] `client.cancel_orchestration()` - cancel running orchestration
- [ ] Async versions of all methods

**Implementation:**
```python
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

class OrchestrationStatus(str, Enum):
    """Status of an orchestration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DAGNode(BaseModel):
    """A node in the orchestration DAG."""
    id: str
    agent_id: str
    capability_id: str
    input_data: Dict[str, Any]
    depends_on: List[str] = []  # IDs of nodes this depends on

class DAGEdge(BaseModel):
    """An edge in the orchestration DAG."""
    from_node: str
    to_node: str
    data_mapping: Optional[Dict[str, str]] = None  # Map output fields to input fields

class OrchestrationRequest(BaseModel):
    """Request to create an orchestration."""
    orchestrator_id: str  # Agent ID of the orchestrator
    task_id: str  # Unique task identifier
    dag: Dict[str, Any]  # {nodes: [...], edges: [...]}
    timeout_seconds: Optional[int] = 300

class Orchestration(BaseModel):
    """Represents an orchestration."""
    id: UUID
    orchestrator_id: str
    task_id: str
    status: OrchestrationStatus
    dag: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# In IntunoClient
def create_orchestration(
    self,
    orchestrator_id: str,
    task_id: str,
    dag: Dict[str, Any],
    timeout_seconds: Optional[int] = None,
) -> Orchestration:
    """Create and start an orchestration."""
    payload = {
        "orchestrator_id": orchestrator_id,
        "task_id": task_id,
        "dag": dag,
    }
    if timeout_seconds:
        payload["timeout_seconds"] = timeout_seconds
    
    response = self._http_client.post("/broker/orchestrations", json=payload)
    response.raise_for_status()
    return Orchestration(**response.json())

def get_orchestration_status(self, orchestration_id: UUID) -> Orchestration:
    """Get the status of an orchestration."""
    response = self._http_client.get(f"/broker/orchestrations/{orchestration_id}")
    response.raise_for_status()
    return Orchestration(**response.json())

def cancel_orchestration(self, orchestration_id: UUID) -> bool:
    """Cancel a running orchestration."""
    response = self._http_client.post(
        f"/broker/orchestrations/{orchestration_id}/cancel"
    )
    response.raise_for_status()
    return True

# Helper method for polling
def wait_for_orchestration(
    self,
    orchestration_id: UUID,
    poll_interval: float = 1.0,
    timeout: Optional[float] = None,
) -> Orchestration:
    """Poll orchestration until completion or timeout."""
    import time
    start_time = time.time()
    
    while True:
        orchestration = self.get_orchestration_status(orchestration_id)
        
        if orchestration.status in [OrchestrationStatus.COMPLETED, OrchestrationStatus.FAILED, OrchestrationStatus.CANCELLED]:
            return orchestration
        
        if timeout and (time.time() - start_time) > timeout:
            raise TimeoutError(f"Orchestration {orchestration_id} timed out")
        
        time.sleep(poll_interval)
```

**3. Helper Utilities**
- [ ] `build_dag_from_workflow()` - helper to build DAG from simple workflow description
- [ ] `validate_dag()` - validate DAG structure (no cycles, etc.)

---

### Pattern 4: Reputation & Trust Signals

#### Changes Needed

**1. Metrics Models** (Priority: High)
- [ ] `AgentMetrics` model
- [ ] `TrustScore` model

**2. Metrics Methods**
- [ ] `client.get_agent_metrics(agent_id)` - get metrics for an agent
- [ ] `agent.get_metrics()` - convenience method
- [ ] `client.submit_feedback(agent_id, rating, comment)` - submit feedback

**Implementation:**
```python
class AgentMetrics(BaseModel):
    """Metrics for an agent."""
    agent_id: str
    success_rate_7d: float = Field(..., ge=0.0, le=1.0)
    avg_latency_ms: float
    error_rate_7d: float = Field(..., ge=0.0, le=1.0)
    total_invocations_7d: int
    trust_score: float = Field(..., ge=0.0, le=1.0)
    total_cost_usd: Optional[float] = None

class AgentFeedback(BaseModel):
    """Feedback for an agent."""
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

# In IntunoClient
def get_agent_metrics(self, agent_id: str) -> AgentMetrics:
    """Get metrics for an agent."""
    response = self._http_client.get(f"/registry/agents/{agent_id}/metrics")
    response.raise_for_status()
    return AgentMetrics(**response.json())

def submit_feedback(
    self,
    agent_id: str,
    rating: int,
    comment: Optional[str] = None,
) -> bool:
    """Submit feedback for an agent."""
    payload = {
        "rating": rating,
        "comment": comment,
    }
    response = self._http_client.post(
        f"/registry/agents/{agent_id}/feedback",
        json=payload,
    )
    response.raise_for_status()
    return True

# Add to Agent model
class Agent(BaseModel):
    # ... existing fields ...
    trust_score: Optional[float] = None  # NEW - from API response
    
    def get_metrics(self) -> AgentMetrics:
        """Get metrics for this agent."""
        if not self._client:
            raise RuntimeError("Client not set on agent")
        return self._client.get_agent_metrics(self.agent_id)
    
    def submit_feedback(self, rating: int, comment: Optional[str] = None) -> bool:
        """Submit feedback for this agent."""
        if not self._client:
            raise RuntimeError("Client not set on agent")
        return self._client.submit_feedback(self.agent_id, rating, comment)
```

---

### Pattern 5: Lightweight Pub/Sub Fabric

#### Changes Needed

**1. Async Invocation Support** (Priority: Medium)
- [ ] `AsyncInvokeOptions` model
- [ ] `InvokeJob` model
- [ ] `client.invoke_async()` - returns job_id
- [ ] `client.get_invoke_job_status(job_id)` - poll async job

**Implementation:**
```python
class AsyncInvokeOptions(BaseModel):
    """Options for async invocation."""
    agent_id: str
    capability_id: str
    input_data: Dict[str, Any]
    webhook_url: Optional[str] = None  # Optional webhook for completion

class InvokeJob(BaseModel):
    """Represents an async invocation job."""
    job_id: UUID
    status: str  # pending, running, completed, failed
    result: Optional[InvokeResult] = None
    created_at: datetime
    updated_at: datetime

# In IntunoClient
def invoke_async(
    self,
    agent_id: str,
    capability_id: str,
    input_data: Dict[str, Any],
    webhook_url: Optional[str] = None,
) -> InvokeJob:
    """Invoke an agent capability asynchronously."""
    payload = {
        "agent_id": agent_id,
        "capability_id": capability_id,
        "input": input_data,
        "async": True,
    }
    if webhook_url:
        payload["webhook_url"] = webhook_url
    
    response = self._http_client.post("/broker/invoke", json=payload)
    response.raise_for_status()
    return InvokeJob(**response.json())

def get_invoke_job_status(self, job_id: UUID) -> InvokeJob:
    """Get the status of an async invocation job."""
    response = self._http_client.get(f"/broker/jobs/{job_id}")
    response.raise_for_status()
    return InvokeJob(**response.json())

# Helper for waiting
def wait_for_invoke_job(
    self,
    job_id: UUID,
    poll_interval: float = 0.5,
    timeout: Optional[float] = None,
) -> InvokeResult:
    """Poll async job until completion."""
    import time
    start_time = time.time()
    
    while True:
        job = self.get_invoke_job_status(job_id)
        
        if job.status == "completed":
            if job.result:
                return job.result
            raise RuntimeError("Job completed but no result")
        
        if job.status == "failed":
            raise InvocationError(f"Async invocation failed: {job.result.error if job.result else 'Unknown error'}")
        
        if timeout and (time.time() - start_time) > timeout:
            raise TimeoutError(f"Job {job_id} timed out")
        
        time.sleep(poll_interval)
```

**2. Webhook Support** (Priority: Low - Future)
- [ ] Webhook subscription helpers (if API provides it)
- [ ] Event listener utilities

---

## Integration Enhancements

### LangChain Integration Updates

**1. Enhanced Discovery Tool**
- [ ] Update `create_discovery_tool()` to support filters
- [ ] Return ranked agents with scores
- [ ] Expose trust scores in tool output

**2. Orchestration Tool**
- [ ] `create_orchestration_tool()` - new tool for LangChain agents to create orchestrations
- [ ] `create_orchestration_status_tool()` - check orchestration status

**3. Metrics Tool**
- [ ] `create_metrics_tool()` - get agent metrics
- [ ] `create_feedback_tool()` - submit feedback

**Implementation:**
```python
def create_orchestration_tool(client: Union[IntunoClient, AsyncIntunoClient]) -> BaseTool:
    """Creates a LangChain Tool for creating orchestrations."""
    class OrchestrationInput(BaseModel):
        orchestrator_id: str = Field(description="Agent ID of the orchestrator")
        task_id: str = Field(description="Unique task identifier")
        dag: Dict[str, Any] = Field(description="DAG definition with nodes and edges")
    
    def _run_sync(orchestrator_id: str, task_id: str, dag: Dict[str, Any]) -> str:
        if not isinstance(client, IntunoClient):
            raise TypeError("A synchronous IntunoClient is required.")
        orchestration = client.create_orchestration(orchestrator_id, task_id, dag)
        return f"Orchestration created: {orchestration.id}. Status: {orchestration.status}"
    
    async def _arun_async(orchestrator_id: str, task_id: str, dag: Dict[str, Any]) -> str:
        if not isinstance(client, AsyncIntunoClient):
            raise TypeError("An asynchronous AsyncIntunoClient is required.")
        orchestration = await client.acreate_orchestration(orchestrator_id, task_id, dag)
        return f"Orchestration created: {orchestration.id}. Status: {orchestration.status}"
    
    return Tool(
        name="intuno_create_orchestration",
        description="Creates a multi-agent orchestration workflow. Use this when you need to chain multiple agent calls together.",
        func=_run_sync,
        coroutine=_arun_async,
        args_schema=OrchestrationInput,
    )
```

### OpenAI Integration Updates

**1. Enhanced Discovery Tool Schema**
- [ ] Update `get_discovery_tool_openai_schema()` to include filter parameters
- [ ] Add ranking options to tool schema

**2. New Tool Schemas**
- [ ] `get_orchestration_tool_openai_schema()`
- [ ] `get_metrics_tool_openai_schema()`
- [ ] `get_feedback_tool_openai_schema()`

---

## Backward Compatibility Strategy

### Migration Path

**1. Discover Method**
- Keep old `discover(query, limit)` signature working
- Add new optional parameters with defaults
- Use `use_ranking=False` to opt into old behavior
- Deprecate old GET endpoint usage (warn in v2.0, remove in v3.0)

**2. Model Updates**
- Add new fields as Optional with None defaults
- Old code continues to work
- New code can access new fields

**3. Versioning**
- Current: v0.1.0 (initial release)
- v0.2.0: Add ranking, metrics, orchestration (backward compatible)
- v1.0.0: Stable API, remove deprecated methods
- v2.0.0: Breaking changes if needed

---

## Implementation Priority

### Phase 1: Critical (Weeks 2-3)
1. ✅ Enhanced `discover()` with ranking and filters
2. ✅ `RankedAgent` and `DiscoverOptions` models
3. ✅ `CapabilityMetadata` model
4. ✅ Update `Agent` and `Capability` models with new fields

### Phase 2: High Priority (Weeks 4-5)
5. ✅ `AgentMetrics` model and `get_agent_metrics()` method
6. ✅ `submit_feedback()` method
7. ✅ Trust score exposure in models

### Phase 3: Medium Priority (Week 6)
8. ✅ Orchestration models and methods
9. ✅ DAG helper utilities
10. ✅ Orchestration LangChain/OpenAI tools

### Phase 4: Nice to Have (Weeks 7-8)
11. ✅ Async invocation support
12. ✅ `refresh_agent_vcv()` method
13. ✅ Enhanced integration tools

---

## Testing Strategy

### Unit Tests
- [ ] Test new models with various data combinations
- [ ] Test backward compatibility of discover method
- [ ] Test orchestration DAG validation
- [ ] Test ranking with different weights

### Integration Tests
- [ ] Test against real API (when available)
- [ ] Test LangChain integration with new tools
- [ ] Test OpenAI integration with new schemas
- [ ] Test async methods

### Example Code
- [ ] Update README with new examples
- [ ] Add orchestration examples
- [ ] Add ranking/filtering examples
- [ ] Add metrics examples

---

## Documentation Updates

### README Updates
- [ ] Add section on ranking and filtering
- [ ] Add orchestration examples
- [ ] Add metrics and trust scores section
- [ ] Update discovery examples with new features

### API Reference
- [ ] Document all new models
- [ ] Document all new methods
- [ ] Add migration guide from v0.1 to v0.2

### Integration Guides
- [ ] Update LangChain integration guide
- [ ] Update OpenAI integration guide
- [ ] Add orchestration guide

---

## Breaking Changes (None in v0.2)

### v0.2.0 (Backward Compatible)
- All changes are additive
- Old code continues to work
- New features are opt-in

### Future v2.0.0 (Potential Breaking Changes)
- Remove old GET `/registry/discover` support
- Require ranking by default
- Make some optional fields required

---

## Example Usage

### Enhanced Discovery with Ranking
```python
from intuno_sdk import IntunoClient, DiscoverFilters, RankingWeights

client = IntunoClient(api_key="...")

# Simple discovery (backward compatible)
agents = client.discover(query="weather forecast")

# Discovery with filters
filters = DiscoverFilters(
    max_cost_usd=0.01,
    max_latency_ms=500,
    min_trust_score=0.7,
)
ranked_agents = client.discover(
    query="translate text",
    filters=filters,
    limit=5,
)

# Custom ranking weights
weights = RankingWeights(
    similarity=0.8,
    latency=0.1,
    cost=0.05,
    trust=0.05,
)
agents = client.discover(
    query="summarize PDF",
    ranking_weights=weights,
)

# Access ranking info
for agent in ranked_agents:
    print(f"{agent.name}: score={agent.score}, latency={agent.estimated_latency_ms}ms")
```

### Orchestration
```python
from intuno_sdk import IntunoClient

client = IntunoClient(api_key="...")

# Create orchestration
dag = {
    "nodes": [
        {"id": "node1", "agent_id": "agent:pdf:summarizer", "capability_id": "summarize"},
        {"id": "node2", "agent_id": "agent:translator", "capability_id": "translate"},
    ],
    "edges": [
        {"from": "node1", "to": "node2", "data_mapping": {"summary": "text"}},
    ],
}

orchestration = client.create_orchestration(
    orchestrator_id="agent:orchestrator:1.0.0",
    task_id="task-123",
    dag=dag,
)

# Poll for completion
result = client.wait_for_orchestration(orchestration.id)
print(f"Orchestration {result.status}: {result.results}")
```

### Metrics and Trust
```python
from intuno_sdk import IntunoClient

client = IntunoClient(api_key="...")

# Get agent metrics
metrics = client.get_agent_metrics("agent:weather:1.0.0")
print(f"Trust score: {metrics.trust_score}")
print(f"Success rate: {metrics.success_rate_7d}")

# Submit feedback
client.submit_feedback(
    agent_id="agent:weather:1.0.0",
    rating=5,
    comment="Very accurate forecasts!"
)

# Access metrics from agent object
agents = client.discover(query="weather")
if agents:
    agent = agents[0]
    metrics = agent.get_metrics()  # Convenience method
    agent.submit_feedback(rating=4)
```

---

## Next Steps

1. **Review this plan** with team
2. **Prioritize features** based on API availability
3. **Start with Phase 1** (ranking and discovery)
4. **Iterate** based on API changes and user feedback

---

## Notes

- All new features should be **backward compatible**
- Use **feature flags** or optional parameters for gradual rollout
- **Type hints** are essential for good DX
- **Comprehensive examples** in README
- **Error handling** should be clear and actionable

