# Intuno SDK Enhancement Priorities

## Quick Reference: What to Build vs What to Skip

### ✅ **BUILD NOW (Phase 1 - Weeks 2-3)**

#### 1. Enhanced Discovery with Ranking ⭐ **CRITICAL**
- [ ] Update `discover()` to support `POST /registry/discover` with filters
- [ ] Add `DiscoverOptions`, `DiscoverFilters`, `RankingWeights` models
- [ ] Add `RankedAgent` model (extends `Agent` with score, latency, cost)
- [ ] Maintain backward compatibility with old GET endpoint
- **Why**: Core feature - makes discovery actually useful
- **Effort**: Medium
- **Impact**: Very High

#### 2. Metadata Models (Phase 1)
- [ ] Add `CapabilityMetadata` model (cost, latency hints)
- [ ] Update `Capability` model to include `metadata` and `vcv_version`
- [ ] Update `Agent` model to include `trust_score` and `vcv_version`
- **Why**: Foundation for ranking and trust features
- **Effort**: Low
- **Impact**: High

---

### ⚠️ **BUILD NEXT (Phase 2 - Weeks 4-5)**

#### 3. Trust Scores & Metrics ⭐ **HIGH PRIORITY**
- [ ] Add `AgentMetrics` model
- [ ] `client.get_agent_metrics(agent_id)` method
- [ ] `agent.get_metrics()` convenience method
- [ ] `client.submit_feedback()` method
- [ ] `agent.submit_feedback()` convenience method
- **Why**: Essential for filtering and ranking
- **Effort**: Medium
- **Impact**: High

---

### ⚠️ **BUILD LATER (Phase 3 - Week 6)**

#### 4. Orchestration Support (Medium Priority)
- [ ] `Orchestration`, `DAGNode`, `DAGEdge` models
- [ ] `client.create_orchestration()` method
- [ ] `client.get_orchestration_status()` method
- [ ] `client.wait_for_orchestration()` helper
- [ ] LangChain/OpenAI orchestration tools
- **Why**: Enables multi-agent workflows
- **Effort**: High
- **Impact**: Medium

---

### ⚠️ **NICE TO HAVE (Phase 4 - Weeks 7-8)**

#### 5. Async Invocation (Medium Priority)
- [ ] `InvokeJob` model
- [ ] `client.invoke_async()` method
- [ ] `client.get_invoke_job_status()` method
- [ ] `client.wait_for_invoke_job()` helper
- **Why**: Better for long-running tasks
- **Effort**: Medium
- **Impact**: Medium

#### 6. VCV Refresh (Low Priority)
- [ ] `client.refresh_agent_vcv()` method
- [ ] Async version
- **Why**: Useful but not critical
- **Effort**: Low
- **Impact**: Low

---

## Priority Matrix

| Feature | Priority | Effort | Impact | Phase |
|---------|----------|--------|--------|-------|
| **Enhanced Discovery** | **Critical** | Medium | **Very High** | 1 |
| **Metadata Models** | **High** | Low | **High** | 1 |
| **Trust & Metrics** | **High** | Medium | **High** | 2 |
| Orchestration | Medium | High | Medium | 3 |
| Async Invocation | Medium | Medium | Medium | 4 |
| VCV Refresh | Low | Low | Low | 4 |

---

## Backward Compatibility Strategy

### ✅ All Changes Are Additive
- Old `discover(query, limit)` still works
- New parameters are optional
- Old models still valid (new fields are Optional)
- No breaking changes in v0.2.0

### Migration Path
```python
# Old code (still works)
agents = client.discover(query="weather", limit=10)

# New code (opt-in)
filters = DiscoverFilters(max_cost_usd=0.01, min_trust_score=0.7)
ranked_agents = client.discover(query="weather", filters=filters, limit=10)
```

---

## Integration Updates Needed

### LangChain
- [ ] Update `create_discovery_tool()` to support filters
- [ ] Add `create_orchestration_tool()`
- [ ] Add `create_metrics_tool()`
- [ ] Update discovery tool to show trust scores

### OpenAI
- [ ] Update `get_discovery_tool_openai_schema()` with filter params
- [ ] Add `get_orchestration_tool_openai_schema()`
- [ ] Add `get_metrics_tool_openai_schema()`

---

## Example: Enhanced Discovery

```python
from intuno_sdk import IntunoClient, DiscoverFilters

client = IntunoClient(api_key="...")

# Simple (backward compatible)
agents = client.discover(query="weather")

# With filters
filters = DiscoverFilters(
    max_cost_usd=0.01,
    max_latency_ms=500,
    min_trust_score=0.7,
)
ranked_agents = client.discover(
    query="translate text",
    filters=filters,
)

# Access ranking info
for agent in ranked_agents:
    print(f"{agent.name}: score={agent.score:.2f}")
    print(f"  Trust: {agent.trust_score:.2f}")
    print(f"  Latency: {agent.estimated_latency_ms}ms")
    print(f"  Cost: ${agent.estimated_cost_usd:.4f}")
```

---

## Example: Orchestration

```python
from intuno_sdk import IntunoClient

client = IntunoClient(api_key="...")

dag = {
    "nodes": [
        {"id": "summarize", "agent_id": "...", "capability_id": "..."},
        {"id": "translate", "agent_id": "...", "capability_id": "..."},
    ],
    "edges": [{"from": "summarize", "to": "translate"}],
}

orchestration = client.create_orchestration(
    orchestrator_id="agent:orchestrator:1.0.0",
    task_id="task-123",
    dag=dag,
)

# Wait for completion
result = client.wait_for_orchestration(orchestration.id)
print(f"Status: {result.status}")
print(f"Results: {result.results}")
```

---

## Example: Metrics

```python
from intuno_sdk import IntunoClient

client = IntunoClient(api_key="...")

# Get metrics
metrics = client.get_agent_metrics("agent:weather:1.0.0")
print(f"Trust: {metrics.trust_score:.2f}")
print(f"Success rate: {metrics.success_rate_7d:.2%}")

# Submit feedback
client.submit_feedback(
    agent_id="agent:weather:1.0.0",
    rating=5,
    comment="Great forecasts!"
)

# From agent object
agents = client.discover(query="weather")
if agents:
    agent = agents[0]
    metrics = agent.get_metrics()  # Convenience
    agent.submit_feedback(rating=4)
```

---

## Testing Checklist

### Unit Tests
- [ ] New models with various data
- [ ] Backward compatibility of discover
- [ ] Ranking with different weights
- [ ] DAG validation

### Integration Tests
- [ ] Real API (when available)
- [ ] LangChain integration
- [ ] OpenAI integration
- [ ] Async methods

### Documentation
- [ ] Update README examples
- [ ] Add orchestration guide
- [ ] Add metrics guide
- [ ] Migration guide v0.1 → v0.2

---

## Versioning Plan

- **v0.1.0**: Current (initial release)
- **v0.2.0**: Add ranking, metrics, orchestration (backward compatible)
- **v1.0.0**: Stable API
- **v2.0.0**: Potential breaking changes (if needed)

---

## Next Actions

1. ✅ Review plan
2. ✅ Start Phase 1: Enhanced discovery (Week 2-3)
3. ✅ Implement metadata models
4. ✅ Test backward compatibility
5. ✅ Update documentation

---

## Key Principles

1. **Backward Compatible**: Old code must continue to work
2. **Opt-in Features**: New features are optional
3. **Type Safety**: Full type hints for better DX
4. **Clear Errors**: Helpful error messages
5. **Good Examples**: Comprehensive examples in README

