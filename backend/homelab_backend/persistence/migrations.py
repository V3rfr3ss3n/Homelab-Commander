"""Ordered additive schema migrations; historical steps remain unchanged."""

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE hosts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
        username TEXT NOT NULL,
        package_provider TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX hosts_address_user_port
        ON hosts(address, username, port);
    """,
    """
    ALTER TABLE hosts ADD COLUMN distribution TEXT;
    ALTER TABLE hosts ADD COLUMN distribution_version TEXT;
    ALTER TABLE hosts ADD COLUMN kernel TEXT;
    ALTER TABLE hosts ADD COLUMN updates INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE hosts ADD COLUMN security_updates INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE hosts ADD COLUMN reboot_required INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE hosts ADD COLUMN status TEXT;
    ALTER TABLE hosts ADD COLUMN checked_at TEXT;

    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error_code TEXT,
        reboot_required INTEGER,
        CHECK (state IN ('queued', 'running', 'success', 'failed'))
    );
    CREATE INDEX jobs_created_at ON jobs(created_at DESC);
    CREATE INDEX jobs_host_created ON jobs(host_id, created_at DESC);

    CREATE TABLE job_logs (
        job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
        output TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE custom_tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('command', 'shell')),
        argv_json TEXT,
        shell_command TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    ALTER TABLE jobs ADD COLUMN custom_task_id TEXT
        REFERENCES custom_tasks(id) ON DELETE SET NULL;
    """,
    """
    ALTER TABLE job_logs RENAME TO old_job_logs;
    ALTER TABLE jobs RENAME TO old_jobs;

    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        exit_code INTEGER,
        error_code TEXT,
        reboot_required INTEGER,
        custom_task_id TEXT REFERENCES custom_tasks(id) ON DELETE SET NULL,
        CHECK (state IN ('queued', 'running', 'success', 'failed', 'cancelled'))
    );
    INSERT INTO jobs (
        id, action, host_id, state, created_at, started_at, finished_at,
        error_code, reboot_required, custom_task_id
    )
    SELECT id, action, host_id, state, created_at, started_at, finished_at,
        error_code, reboot_required, custom_task_id
    FROM old_jobs;

    CREATE TABLE job_logs (
        job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
        output TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO job_logs(job_id, output, truncated)
        SELECT job_id, output, truncated FROM old_job_logs;

    DROP TABLE old_job_logs;
    DROP TABLE old_jobs;
    CREATE INDEX jobs_created_at ON jobs(created_at DESC);
    CREATE INDEX jobs_host_created ON jobs(host_id, created_at DESC);
    """,
    """
    ALTER TABLE custom_tasks ADD COLUMN requirements_json TEXT NOT NULL DEFAULT '{}';
    CREATE TABLE task_assignments (
        task_id TEXT NOT NULL REFERENCES custom_tasks(id) ON DELETE CASCADE,
        host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
        enabled INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(task_id, host_id)
    );
    INSERT INTO task_assignments(task_id, host_id, enabled)
        SELECT custom_tasks.id, hosts.id, custom_tasks.enabled
        FROM custom_tasks CROSS JOIN hosts;
    CREATE TABLE task_checks (
        task_id TEXT NOT NULL REFERENCES custom_tasks(id) ON DELETE CASCADE,
        host_id TEXT NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
        fingerprint TEXT NOT NULL,
        result_json TEXT NOT NULL,
        PRIMARY KEY(task_id, host_id)
    );
    """,
    """
    ALTER TABLE hosts ADD COLUMN websites_json TEXT NOT NULL DEFAULT '[]';
    CREATE TABLE ui_preferences (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        auto_check_enabled INTEGER NOT NULL CHECK(auto_check_enabled IN (0,1))
    );
    INSERT INTO ui_preferences(id,auto_check_enabled) VALUES (1,1);
    CREATE TABLE ui_auto_checks (
        host_id TEXT PRIMARY KEY REFERENCES hosts(id) ON DELETE CASCADE,
        requested_at TEXT NOT NULL
    );
    """,
    """
    ALTER TABLE jobs ADD COLUMN reviewed_at TEXT;
    """,
    """
    ALTER TABLE hosts ADD COLUMN packages_json TEXT NOT NULL DEFAULT '[]';
    """,
    """
    ALTER TABLE jobs ADD COLUMN package_name TEXT;
    """,
    """
    ALTER TABLE jobs ADD COLUMN package_names_json TEXT NOT NULL DEFAULT '[]';
    """,
    """
    CREATE TABLE resources (
        id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN
    ('host','managed_service','virtual_machine','container')),
        name TEXT NOT NULL,
        provider_id TEXT,
        connection_id TEXT,
        external_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT,
    CHECK ((kind='host' AND provider_id IS NULL AND connection_id IS NULL AND
    external_id IS NULL)
    OR (kind!='host' AND provider_id IS NOT NULL AND connection_id IS NOT NULL
    AND external_id IS NOT NULL))
    );
    CREATE UNIQUE INDEX resources_active_binding ON
    resources(provider_id,connection_id,external_id)
        WHERE deleted_at IS NULL;
    CREATE TABLE managed_services (
        resource_id TEXT PRIMARY KEY REFERENCES resources(id),
        service_type TEXT NOT NULL,
        host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL
    );
    CREATE TABLE resource_relationships (
    kind TEXT NOT NULL CHECK(kind IN
    ('runs_service','hosts_instance','corresponds_to_host','managed_by')),
        source_id TEXT NOT NULL REFERENCES resources(id),
        target_id TEXT NOT NULL REFERENCES resources(id),
        PRIMARY KEY(kind,source_id,target_id),
        CHECK(source_id!=target_id)
    );
    CREATE UNIQUE INDEX service_single_host ON
    resource_relationships(kind,target_id) WHERE kind='runs_service';
    CREATE UNIQUE INDEX instance_single_host ON
    resource_relationships(kind,source_id) WHERE kind='corresponds_to_host';
    CREATE UNIQUE INDEX host_single_instance ON
    resource_relationships(kind,target_id) WHERE kind='corresponds_to_host';
    INSERT INTO resources(id,kind,name,created_at,updated_at)
        SELECT id,'host',name,created_at,updated_at FROM hosts;
    CREATE TRIGGER hosts_resource_created AFTER INSERT ON hosts BEGIN
        INSERT INTO resources(id,kind,name,created_at,updated_at)
            VALUES(NEW.id,'host',NEW.name,NEW.created_at,NEW.updated_at);
    END;
    CREATE TRIGGER hosts_resource_renamed AFTER UPDATE OF name ON hosts BEGIN
        UPDATE resources SET name=NEW.name,updated_at=NEW.updated_at WHERE id=NEW.id;
    END;
    CREATE TRIGGER hosts_resource_removed BEFORE DELETE ON hosts BEGIN
    UPDATE resources SET deleted_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE
    id=OLD.id;
        DELETE FROM resource_relationships WHERE source_id=OLD.id OR target_id=OLD.id;
    END;
    """,
    """
    CREATE TABLE resource_groups (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        rule_json TEXT
    );
    CREATE TABLE group_members (
        group_id TEXT NOT NULL REFERENCES resource_groups(id) ON DELETE CASCADE,
        resource_id TEXT NOT NULL REFERENCES resources(id),
        PRIMARY KEY(group_id,resource_id)
    );
    CREATE INDEX group_members_resource ON group_members(resource_id);
    CREATE TABLE resource_tags (
        resource_id TEXT NOT NULL REFERENCES resources(id),
        tag TEXT NOT NULL,
        PRIMARY KEY(resource_id,tag)
    );
    CREATE INDEX resource_tags_tag ON resource_tags(tag,resource_id);
    """,
)
