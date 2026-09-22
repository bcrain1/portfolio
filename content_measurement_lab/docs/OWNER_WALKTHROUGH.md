# Ten-minute review before sharing

This is an AI-assisted independent demonstration. Review it before representing
it as work you can discuss and maintain. No claim of owner acceptance is recorded.

1. Open output/dashboard.html. Explain why 406 members are excluded from rates.
2. Compare the exposed and unexposed return rates. Explain why the 30.4-point
   difference is not an incremental product effect.
3. Filter to frequent viewers, then occasional viewers. Explain the audience
   mix change. Reset and explain the common weighting used for standardization.
4. Filter to August 25-28. The dashboard should show no mature cohort, with
   unavailable rates rather than zero-percent return.
5. Read sql/03_member_metrics.sql. Explain why eligibility anchors both groups,
   why EXISTS avoids fanout, and what happens exactly at 24h and 168h.
6. Read a duplicate and conflict test. Explain why one retry is removed while
   every conflicting-ID delivery is quarantined.
7. Explain why a missing heartbeat is not necessarily an unengaged viewer.
8. Explain what the Wilson intervals do and do not tell a decision-maker.
9. Run the test command in README. Change the engagement threshold to 900
   seconds in a copy and identify every label/definition that must change too.
10. State the next decision: verify measurement, then design an experiment.
    Describe which alternative metrics would stop an otherwise appealing rollout.

Keep the existing project samples described as synthetic demos too. They are
not evidence of paid clients or past production deployment. This owner-approved
public repository shares the lab and its walkthrough; review the work before
representing it as demonstrated competence.
