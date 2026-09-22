CREATE TABLE settings(as_of INTEGER NOT NULL);
CREATE TABLE members(member_id TEXT PRIMARY KEY, eligible_s INTEGER NOT NULL,
                     pre_period_active_days INTEGER NOT NULL CHECK(pre_period_active_days BETWEEN 0 AND 14));
CREATE TABLE events(event_id TEXT PRIMARY KEY, member_id TEXT NOT NULL REFERENCES members,
                    event_s INTEGER NOT NULL, received_s INTEGER NOT NULL,
                    event_type TEXT NOT NULL, content_type TEXT NOT NULL, device TEXT NOT NULL,
                    watched_seconds INTEGER NOT NULL CHECK(watched_seconds BETWEEN 0 AND 60));
CREATE INDEX event_member_time ON events(member_id,event_s);
