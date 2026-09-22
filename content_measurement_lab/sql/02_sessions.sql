-- Member + device + content boundary. An explicit play always starts a session.
-- Orphan telemetry gets a session for observability but never counts as a play.
CREATE TABLE sessions AS
WITH ordered AS (
 SELECT *, LAG(event_s) OVER w AS previous_s, LAG(content_type) OVER w AS previous_content
 FROM events WHERE event_type <> 'exposure'
 WINDOW w AS (PARTITION BY member_id,device ORDER BY event_s,CASE WHEN event_type='play' THEN 0 ELSE 1 END,event_id)
), boundaries AS (
 SELECT *, CASE WHEN previous_s IS NULL OR event_s-previous_s>1800
   OR previous_content<>content_type OR event_type='play' THEN 1 ELSE 0 END AS new_session
 FROM ordered
), numbered AS (
 SELECT *, SUM(new_session) OVER (PARTITION BY member_id,device ORDER BY event_s,CASE WHEN event_type='play' THEN 0 ELSE 1 END,event_id
   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_number FROM boundaries
)
SELECT member_id,device,session_number,MIN(event_s) AS start_s,MAX(event_s) AS end_s,
 MAX(content_type) AS content_type,
 SUM(event_type='play') AS plays,SUM(event_type='heartbeat') AS heartbeats,
 SUM(event_type='playback_error') AS errors,
 SUM(CASE WHEN event_type='heartbeat' THEN watched_seconds ELSE 0 END) AS observed_watch_seconds
FROM numbered GROUP BY member_id,device,session_number;
