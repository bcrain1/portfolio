-- Grain: one accepted service/scenario/hour. Identical windows across comparisons.
SELECT scenario, service,
       COUNT(*) AS windows,
       SUM(requested_tasks) AS requested_tasks,
       SUM(successful_tasks) AS successful_tasks,
       SUM(failed_tasks) AS failed_tasks,
       SUM(retry_attempts) AS retry_attempts,
       SUM(cpu_allocated_millihours) AS cpu_allocated_millihours,
       SUM(cpu_busy_millihours) AS cpu_busy_millihours,
       SUM(cpu_cost_micro) AS cpu_cost_micro,
       SUM(memory_cost_micro) AS memory_cost_micro,
       SUM(storage_cost_micro) AS storage_cost_micro,
       SUM(shared_cost_micro) AS shared_cost_micro,
       SUM(idle_cpu_cost_micro) AS idle_cpu_cost_micro,
       SUM(total_cost_micro) AS total_cost_micro,
       MAX(interval_p95_ms) AS worst_interval_p95_ms
FROM ledger
GROUP BY scenario, service
ORDER BY scenario, service;
