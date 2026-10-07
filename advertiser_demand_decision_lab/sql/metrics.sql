-- One initial planning attempt per advertiser; EXISTS prevents telemetry fanout.
SELECT a.*,
 EXISTS(SELECT 1 FROM events e WHERE e.advertiser_id=a.advertiser_id AND e.kind='plan_completed') AS plan_completed,
 EXISTS(SELECT 1 FROM events e WHERE e.advertiser_id=a.advertiser_id AND e.kind='campaign_launched') AS campaign_launched
FROM advertisers a ORDER BY advertiser_id;
