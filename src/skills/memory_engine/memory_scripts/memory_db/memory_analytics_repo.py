import datetime


_ARRAY_COLUMNS = ("projects", "tags", "people", "technologies")


def ensure_schema(conn) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_summaries (
                date DATE PRIMARY KEY,
                weekday SMALLINT NOT NULL,
                mood TEXT,
                projects TEXT[],
                tags TEXT[],
                people TEXT[],
                technologies TEXT[],
                importance SMALLINT,
                summary_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS daily_summaries_weekday_idx ON daily_summaries (weekday);")
        cur.execute("CREATE INDEX IF NOT EXISTS daily_summaries_projects_gin_idx ON daily_summaries USING GIN (projects);")
        cur.execute("CREATE INDEX IF NOT EXISTS daily_summaries_tags_gin_idx ON daily_summaries USING GIN (tags);")
        cur.execute("CREATE INDEX IF NOT EXISTS daily_summaries_people_gin_idx ON daily_summaries USING GIN (people);")
        cur.execute("CREATE INDEX IF NOT EXISTS daily_summaries_technologies_gin_idx ON daily_summaries USING GIN (technologies);")
        conn.commit()
    finally:
        cur.close()


def upsert_daily_summary(conn, row: dict) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO daily_summaries (
                date, weekday, mood, projects, tags, people, technologies, importance, summary_path, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (date) DO UPDATE SET
                weekday = EXCLUDED.weekday,
                mood = EXCLUDED.mood,
                projects = EXCLUDED.projects,
                tags = EXCLUDED.tags,
                people = EXCLUDED.people,
                technologies = EXCLUDED.technologies,
                importance = EXCLUDED.importance,
                summary_path = EXCLUDED.summary_path,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (
                row["date"],
                row["weekday"],
                row.get("mood"),
                row.get("projects") or [],
                row.get("tags") or [],
                row.get("people") or [],
                row.get("technologies") or [],
                row.get("importance"),
                row["summary_path"],
            ),
        )
    finally:
        cur.close()


def get_existing_dates(conn) -> set[datetime.date]:
    """Return all dates already in the daily_summaries table."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT date FROM daily_summaries;")
        return {r[0] for r in cur.fetchall()}
    finally:
        cur.close()


def get_latest_date(conn) -> datetime.date | None:
    """Return the most recent date in daily_summaries, or None."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(date) FROM daily_summaries;")
        row = cur.fetchone()
        return row[0] if row and row[0] else None
    finally:
        cur.close()


def get_dates_for_array_value(conn, column: str, value: str) -> list[datetime.date]:
    if column not in _ARRAY_COLUMNS:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT date
            FROM daily_summaries
            WHERE EXISTS (
                SELECT 1 FROM unnest({column}) v WHERE lower(v) = lower(%s)
            )
            ORDER BY date ASC;
            """,
            (value,),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        cur.close()


def get_mood_distribution_by_weekday(conn, weekday: int) -> list[tuple[str, int]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(mood, '(none)') AS mood, COUNT(*) AS count
            FROM daily_summaries
            WHERE weekday = %s
            GROUP BY mood
            ORDER BY count DESC, mood ASC;
            """,
            (weekday,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()


def get_mood_timeseries(conn, start_date: datetime.date, end_date: datetime.date) -> list[tuple[datetime.date, str]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT date, COALESCE(mood, '(none)') AS mood
            FROM daily_summaries
            WHERE date BETWEEN %s AND %s
            ORDER BY date ASC;
            """,
            (start_date, end_date),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()


def get_top_values(
    conn,
    column: str,
    start_date: datetime.date,
    end_date: datetime.date,
    limit: int = 20,
) -> list[tuple[str, int]]:
    if column not in _ARRAY_COLUMNS:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT val, COUNT(*) AS count
            FROM (
                SELECT unnest({column}) AS val
                FROM daily_summaries
                WHERE date BETWEEN %s AND %s
            ) t
            WHERE val IS NOT NULL AND val <> ''
            GROUP BY val
            ORDER BY count DESC, val ASC
            LIMIT %s;
            """,
            (start_date, end_date, limit),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()


def count_distinct_dates_for_array_value(
    conn,
    column: str,
    value: str,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> int:
    if column not in _ARRAY_COLUMNS:
        return 0
    cur = conn.cursor()
    try:
        query = f"""
            SELECT COUNT(*)
            FROM daily_summaries
            WHERE EXISTS (
                SELECT 1 FROM unnest({column}) v WHERE lower(v) = lower(%s)
            )
        """
        params = [value]
        if start_date and end_date:
            query += " AND date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        cur.close()


def get_count_by_period(
    conn,
    column: str,
    value: str,
    period: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> list[tuple[datetime.date, int]]:
    if column not in _ARRAY_COLUMNS or period not in ("day", "week", "month"):
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT date_trunc(%s, date)::date AS bucket, COUNT(*) AS count
            FROM daily_summaries
            WHERE date BETWEEN %s AND %s
              AND EXISTS (
                SELECT 1 FROM unnest({column}) v WHERE lower(v) = lower(%s)
              )
            GROUP BY bucket
            ORDER BY bucket ASC;
            """,
            (period, start_date, end_date, value),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()


def get_grouped_top_values(
    conn,
    column: str,
    period: str,
    start_date: datetime.date,
    end_date: datetime.date,
    limit: int = 10,
) -> list[tuple[datetime.date, str, int]]:
    if column not in _ARRAY_COLUMNS or period not in ("day", "week", "month"):
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            WITH ranked AS (
                SELECT
                    date_trunc(%s, date)::date AS bucket,
                    val,
                    COUNT(*) AS count,
                    ROW_NUMBER() OVER (
                        PARTITION BY date_trunc(%s, date)::date
                        ORDER BY COUNT(*) DESC, val ASC
                    ) AS rn
                FROM (
                    SELECT date, unnest({column}) AS val
                    FROM daily_summaries
                    WHERE date BETWEEN %s AND %s
                ) t
                WHERE val IS NOT NULL AND val <> ''
                GROUP BY bucket, val
            )
            SELECT bucket, val, count
            FROM ranked
            WHERE rn <= %s
            ORDER BY bucket ASC, count DESC, val ASC;
            """,
            (period, period, start_date, end_date, limit),
        )
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]
    finally:
        cur.close()


def get_average_importance(
    conn,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    column: str | None = None,
    value: str | None = None,
) -> tuple[float | None, int]:
    if column is not None and column not in _ARRAY_COLUMNS:
        return None, 0
    cur = conn.cursor()
    try:
        query = """
            SELECT AVG(importance)::float, COUNT(*)
            FROM daily_summaries
            WHERE importance IS NOT NULL
        """
        params = []
        if start_date and end_date:
            query += " AND date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        if column and value:
            query += f"""
             AND EXISTS (
                SELECT 1 FROM unnest({column}) v WHERE lower(v) = lower(%s)
             )
            """
            params.append(value)
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        if not row:
            return None, 0
        avg_value, count = row
        return (float(avg_value), int(count)) if avg_value is not None else (None, int(count or 0))
    finally:
        cur.close()
