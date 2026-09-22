-- One row per eligible member. EXISTS prevents fanout across telemetry rows.
-- First-day exposure/engagement and day 2-7 return share the SAME eligibility anchor.
CREATE TABLE member_metrics AS
SELECT m.member_id, date(m.eligible_s,'unixepoch') AS eligible_date,
 CASE WHEN pre_period_active_days>=5 THEN 'frequent' ELSE 'occasional' END AS baseline_tier,
 CAST(m.eligible_s+604800<=c.as_of AS INTEGER) AS mature,
 CAST(EXISTS(SELECT 1 FROM events e WHERE e.member_id=m.member_id AND e.event_type='exposure'
   AND e.content_type='live' AND e.event_s>=m.eligible_s AND e.event_s<m.eligible_s+3600) AS INTEGER) AS exposed,
 CAST(EXISTS(SELECT 1 FROM sessions s WHERE s.member_id=m.member_id AND s.content_type='live'
   AND s.plays>0 AND s.start_s>=m.eligible_s AND s.start_s<m.eligible_s+86400) AS INTEGER) AS live_started,
 CAST(EXISTS(SELECT 1 FROM sessions s WHERE s.member_id=m.member_id AND s.content_type='live'
   AND s.plays>0 AND s.start_s>=m.eligible_s AND s.start_s<m.eligible_s+86400
   AND s.observed_watch_seconds>=600) AS INTEGER) AS live_engaged,
 CAST(EXISTS(SELECT 1 FROM sessions s WHERE s.member_id=m.member_id AND s.plays>0
   AND s.start_s>m.eligible_s+86400 AND s.start_s<=m.eligible_s+604800) AS INTEGER) AS returned,
 CAST(EXISTS(SELECT 1 FROM sessions s WHERE s.member_id=m.member_id AND s.content_type='live'
   AND s.plays>0 AND s.errors>0 AND s.start_s>=m.eligible_s AND s.start_s<m.eligible_s+86400) AS INTEGER) AS live_error
FROM members m CROSS JOIN settings c WHERE m.eligible_s<=c.as_of;
