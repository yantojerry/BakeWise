from datetime import datetime

from database.db import get_connection


class UserDB:

    @staticmethod
    def _quote_identifier(identifier):
        return f"`{str(identifier).replace('`', '``')}`"

    @staticmethod
    def _table_exists(cursor, table_name):
        cursor.execute(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            LIMIT 1
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _table_columns(cursor, table_name):
        cursor.execute(
            """
            SELECT COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        return {row["COLUMN_NAME"]: row for row in cursor.fetchall()}

    @staticmethod
    def _user_pk(columns):
        if "id" in columns:
            return "id"
        if "user_id" in columns:
            return "user_id"
        raise ValueError("Users table must have either id or user_id.")

    @staticmethod
    def _first_column(columns, names):
        for name in names:
            if name in columns:
                return name
        return None

    @staticmethod
    def _user_select_fields(columns):
        pk = UserDB._quote_identifier(UserDB._user_pk(columns))
        username_col = UserDB._first_column(columns, ("username", "email"))
        name_col = UserDB._first_column(columns, ("name", "full_name"))
        email_col = UserDB._first_column(columns, ("email",))
        contact_col = UserDB._first_column(columns, ("contact_number", "contact", "phone", "mobile"))

        fields = [
            f"u.{pk} AS user_id",
            f"u.{pk} AS id",
            f"u.{UserDB._quote_identifier(username_col)} AS username" if username_col else "'' AS username",
            "u.password AS password" if "password" in columns else "'' AS password",
            "u.role AS role" if "role" in columns else "'cashier' AS role",
            "u.is_active AS is_active" if "is_active" in columns else "1 AS is_active",
            "u.created_at AS created_at" if "created_at" in columns else "NULL AS created_at",
            "u.updated_at AS updated_at" if "updated_at" in columns else (
                "u.created_at AS updated_at" if "created_at" in columns else "NULL AS updated_at"
            ),
        ]

        if name_col and username_col:
            fields.append(
                f"COALESCE(NULLIF(u.{UserDB._quote_identifier(name_col)}, ''), "
                f"u.{UserDB._quote_identifier(username_col)}) AS name"
            )
        elif name_col:
            fields.append(f"u.{UserDB._quote_identifier(name_col)} AS name")
        elif username_col:
            fields.append(f"u.{UserDB._quote_identifier(username_col)} AS name")
        else:
            fields.append("'' AS name")

        fields.append(f"u.{UserDB._quote_identifier(email_col)} AS email" if email_col else "NULL AS email")
        fields.append(
            f"u.{UserDB._quote_identifier(contact_col)} AS contact_number" if contact_col else "NULL AS contact_number"
        )

        if "status" in columns:
            fields.append("u.status AS status")
        elif "is_active" in columns:
            fields.append("CASE WHEN u.is_active = 1 THEN 'Active' ELSE 'Inactive' END AS status")
        else:
            fields.append("NULL AS status")

        return fields

    @staticmethod
    def ensure_session_schema():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            if not UserDB._table_exists(cursor, "user_sessions"):
                return
            user_pk = UserDB._user_pk(UserDB._table_columns(cursor, "users"))
            quoted_user_pk = UserDB._quote_identifier(user_pk)
            cursor.execute(
                """
                SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'user_sessions'
                  AND COLUMN_NAME = 'user_id'
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                """
            )
            constraints = cursor.fetchall()

            for constraint in constraints:
                if (
                    constraint["REFERENCED_TABLE_NAME"] != "users"
                    or constraint["REFERENCED_COLUMN_NAME"] != user_pk
                ):
                    name = UserDB._quote_identifier(constraint["CONSTRAINT_NAME"])
                    cursor.execute(f"ALTER TABLE user_sessions DROP FOREIGN KEY {name}")

            cursor.execute(
                """
                DELETE us
                FROM user_sessions us
                LEFT JOIN users u ON u.%s = us.user_id
                WHERE u.%s IS NULL
                """ % (quoted_user_pk, quoted_user_pk)
            )

            cursor.execute(
                """
                SELECT CONSTRAINT_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'user_sessions'
                  AND COLUMN_NAME = 'user_id'
                  AND REFERENCED_TABLE_NAME = 'users'
                  AND REFERENCED_COLUMN_NAME = %s
                """,
                (user_pk,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    ALTER TABLE user_sessions
                    ADD CONSTRAINT fk_user_sessions_current_user
                    FOREIGN KEY (user_id) REFERENCES users(%s)
                    ON DELETE CASCADE
                    """ % quoted_user_pk
                )

            conn.commit()
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_user(username, prefer_direct=False):
        conn = None
        cursor = None
        try:
            conn = get_connection(prefer_direct=prefer_direct)
            cursor = conn.cursor(dictionary=True)

            columns = UserDB._table_columns(cursor, "users")
            login_col = UserDB._first_column(columns, ("username", "email"))
            if not login_col:
                return None

            fields = UserDB._user_select_fields(columns)
            query = f"""
                SELECT
                    {', '.join(fields)}
                FROM users u
                WHERE u.{UserDB._quote_identifier(login_col)} = %s
            """
            cursor.execute(query, (username,))

            return cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


    @staticmethod
    def add_user(username, password, role, name=None, contact_number=None, status=None):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            columns = UserDB._table_columns(cursor, "users")
            insert_columns = []
            values = []

            pk_col = UserDB._user_pk(columns)
            pk_info = columns.get(pk_col, {})
            next_id = None
            if "auto_increment" not in str(pk_info.get("EXTRA") or "").lower():
                quoted_pk = UserDB._quote_identifier(pk_col)
                cursor.execute(f"SELECT COALESCE(MAX({quoted_pk}), 0) + 1 AS next_id FROM users")
                row = cursor.fetchone() or {}
                next_id = int(row.get("next_id") or 1)
                insert_columns.append(pk_col)
                values.append(next_id)

            if "name" in columns:
                insert_columns.append("name")
                values.append(name or username)
            elif "full_name" in columns:
                insert_columns.append("full_name")
                values.append(name or username)

            if "username" in columns:
                insert_columns.append("username")
                values.append(username)
            elif "email" in columns:
                insert_columns.append("email")
                values.append(username)

            if "password" in columns:
                insert_columns.append("password")
                values.append(password)
            if "role" in columns:
                insert_columns.append("role")
                values.append(role)

            contact_col = UserDB._first_column(columns, ("contact_number", "contact", "phone", "mobile"))
            if contact_col and contact_number:
                insert_columns.append(contact_col)
                values.append(contact_number)

            if "status" in columns:
                insert_columns.append("status")
                values.append(status or "Active")
            elif "is_active" in columns:
                insert_columns.append("is_active")
                values.append(0 if str(status or "").strip().lower() == "inactive" else 1)

            quoted_columns = ", ".join(UserDB._quote_identifier(col) for col in insert_columns)
            placeholders = ", ".join(["%s"] * len(insert_columns))
            query = f"INSERT INTO users ({quoted_columns}) VALUES ({placeholders})"
            cursor.execute(query, tuple(values))

            conn.commit()
            return cursor.lastrowid or next_id
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_all_users():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            columns = UserDB._table_columns(cursor, "users")
            pk_col = UserDB._user_pk(columns)
            quoted_pk = UserDB._quote_identifier(pk_col)
            fields = UserDB._user_select_fields(columns)
            fields.append(f"CONCAT('USR-', LPAD(u.{quoted_pk}, 3, '0')) AS user_code")

            joins = []
            session_columns = (
                UserDB._table_columns(cursor, "user_sessions")
                if UserDB._table_exists(cursor, "user_sessions")
                else {}
            )
            has_sessions = {"user_id", "session_id"}.issubset(session_columns)
            if has_sessions:
                joins.append(
                    """
                    LEFT JOIN (
                        SELECT us.*
                        FROM user_sessions us
                        INNER JOIN (
                            SELECT user_id, MAX(session_id) AS session_id
                            FROM user_sessions
                            GROUP BY user_id
                        ) latest_ids ON latest_ids.session_id = us.session_id
                    ) latest ON latest.user_id = u.%s
                    """ % quoted_pk
                )
                if "login_at" in session_columns and "logout_at" in session_columns:
                    fields.append(
                        "CASE WHEN latest.logout_at IS NULL AND latest.login_at IS NOT NULL THEN 1 ELSE 0 END AS is_online"
                    )
                else:
                    fields.append("0 AS is_online")
                fields.append("latest.login_at AS last_login_at" if "login_at" in session_columns else "NULL AS last_login_at")
                fields.append("latest.logout_at AS last_logout_at" if "logout_at" in session_columns else "NULL AS last_logout_at")
                fields.append("latest.last_screen AS last_screen" if "last_screen" in session_columns else "NULL AS last_screen")
            else:
                log_columns = (
                    UserDB._table_columns(cursor, "login_logs")
                    if UserDB._table_exists(cursor, "login_logs")
                    else {}
                )
                if {"user_id", "timestamp"}.issubset(log_columns):
                    joins.append(
                        """
                        LEFT JOIN (
                            SELECT user_id, MAX(timestamp) AS last_login_at
                            FROM login_logs
                            GROUP BY user_id
                        ) latest_log ON latest_log.user_id = u.%s
                        """ % quoted_pk
                    )
                    fields.append("latest_log.last_login_at AS last_login_at")
                else:
                    fields.append("NULL AS last_login_at")
                fields.extend([
                    "0 AS is_online",
                    "NULL AS last_logout_at",
                    "NULL AS last_screen",
                ])

            cursor.execute(f"""
                SELECT
                    {', '.join(fields)}
                FROM users u
                {' '.join(joins)}
                ORDER BY u.{quoted_pk} ASC
            """)

            return cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_recent_user_history(user_id, limit=8):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            if not UserDB._table_exists(cursor, "user_sessions"):
                return []
            cursor.execute(
                """
                SELECT
                    session_id,
                    user_id,
                    login_at,
                    logout_at,
                    last_screen,
                    session_source,
                    TIMESTAMPDIFF(SECOND, login_at, COALESCE(logout_at, NOW())) AS duration_seconds
                FROM user_sessions
                WHERE user_id = %s
                ORDER BY login_at DESC, session_id DESC
                LIMIT %s
                """,
                (int(user_id), int(limit)),
            )
            return cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def update_user(user_id, password=None, role=None, name=None, contact_number=None, status=None):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            columns = UserDB._table_columns(cursor, "users")
            pk_col = UserDB._user_pk(columns)
            updates = []
            values = []
            if password and "password" in columns:
                updates.append(f"{UserDB._quote_identifier('password')} = %s")
                values.append(password)
            if role and "role" in columns:
                updates.append(f"{UserDB._quote_identifier('role')} = %s")
                values.append(role)
            if name:
                name_col = UserDB._first_column(columns, ("name", "full_name"))
                if name_col:
                    updates.append(f"{UserDB._quote_identifier(name_col)} = %s")
                    values.append(name)
            if contact_number:
                contact_col = UserDB._first_column(columns, ("contact_number", "contact", "phone", "mobile"))
                if contact_col:
                    updates.append(f"{UserDB._quote_identifier(contact_col)} = %s")
                    values.append(contact_number)
            if status:
                if "status" in columns:
                    updates.append(f"{UserDB._quote_identifier('status')} = %s")
                    values.append(status)
                elif "is_active" in columns:
                    updates.append(f"{UserDB._quote_identifier('is_active')} = %s")
                    values.append(0 if str(status).strip().lower() == "inactive" else 1)

            if not updates:
                return 0

            values.append(int(user_id))
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE {UserDB._quote_identifier(pk_col)} = %s",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def start_session(user_id, username=None, role=None, last_screen="dashboard"):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            session_id = None

            if UserDB._table_exists(cursor, "user_sessions"):
                cursor.execute(
                    """
                    INSERT INTO user_sessions (user_id, last_screen, session_source)
                    VALUES (%s, %s, %s)
                    """,
                    (int(user_id), last_screen, "desktop_app"),
                )
                session_id = cursor.lastrowid

            if (username or role) and UserDB._table_exists(cursor, "login_logs"):
                cursor.execute(
                    """
                    INSERT INTO login_logs (user_id, username, role, timestamp)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        int(user_id),
                        username,
                        role,
                        datetime.now().replace(microsecond=0).isoformat(),
                    ),
                )

            conn.commit()
            return session_id
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def update_session_screen(session_id, last_screen):
        if not session_id:
            return
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            if not UserDB._table_exists(cursor, "user_sessions"):
                return
            cursor.execute(
                "UPDATE user_sessions SET last_screen = %s WHERE session_id = %s AND logout_at IS NULL",
                (last_screen, int(session_id)),
            )
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def end_session(session_id):
        if not session_id:
            return
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            if not UserDB._table_exists(cursor, "user_sessions"):
                return
            cursor.execute(
                """
                UPDATE user_sessions
                SET logout_at = NOW()
                WHERE session_id = %s AND logout_at IS NULL
                """,
                (int(session_id),),
            )
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def delete_user(user_id, acting_user_id=None):
        conn = None
        cursor = None
        try:
            target_id = int(user_id)
            if acting_user_id is not None and target_id == int(acting_user_id):
                raise ValueError("You cannot delete the account you are currently signed in with.")

            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            columns = UserDB._table_columns(cursor, "users")
            pk_col = UserDB._user_pk(columns)
            quoted_pk = UserDB._quote_identifier(pk_col)

            cursor.execute(f"SELECT {quoted_pk} FROM users WHERE {quoted_pk} = %s", (target_id,))
            if cursor.fetchone() is None:
                raise ValueError("User account was not found.")

            if UserDB._table_exists(cursor, "user_sessions"):
                cursor.execute("DELETE FROM user_sessions WHERE user_id = %s", (target_id,))
            if UserDB._table_exists(cursor, "login_logs"):
                cursor.execute("DELETE FROM login_logs WHERE user_id = %s", (target_id,))
            cursor.execute(f"DELETE FROM users WHERE {quoted_pk} = %s", (target_id,))

            conn.commit()
            return cursor.rowcount
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
