"""
Ma'lumotlar bazasi moduli — yangilangan versiya
SQLite ishlatiladi
Rollar: admin, worker, user
"""
import sqlite3
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path: str = "shop.db"):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    full_name TEXT,
                    username TEXT,
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS worker_passwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    password TEXT NOT NULL,
                    created_by INTEGER,
                    used_by INTEGER DEFAULT NULL,
                    is_used BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    has_sizes BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT,
                    category_id INTEGER,
                    photo_id TEXT,
                    sizes TEXT DEFAULT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                );

                CREATE TABLE IF NOT EXISTS cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    size TEXT DEFAULT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    customer_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    payment TEXT NOT NULL,
                    delivery TEXT DEFAULT NULL,
                    total INTEGER NOT NULL,
                    discount_pct INTEGER DEFAULT 0,
                    discount_amt INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    size TEXT DEFAULT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                );

                CREATE TABLE IF NOT EXISTS site_admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'worker',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    admin_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES site_admins(id)
                );
            """)
        print("✅ Database initialized")

        try:
            with self.get_connection() as conn:
                conn.execute("ALTER TABLE products ADD COLUMN sizes TEXT DEFAULT NULL")
            print("✅ Migration: sizes ustuni qo'shildi")
        except Exception:
            pass

        try:
            with self.get_connection() as conn:
                conn.execute("ALTER TABLE products ADD COLUMN photo_url TEXT DEFAULT NULL")
            print("✅ Migration: photo_url ustuni qo'shildi")
        except Exception:
            pass

        try:
            with self.get_connection() as conn:
                conn.execute("ALTER TABLE orders ADD COLUMN delivery TEXT DEFAULT NULL")
            print("✅ Migration: delivery ustuni qo'shildi")
        except Exception:
            pass

    def add_user(self, telegram_id: int, full_name: str, username: str = None):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id, full_name, username) VALUES (?, ?, ?)",
                (telegram_id, full_name, username)
            )

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_role(self, telegram_id: int) -> str:
        user = self.get_user(telegram_id)
        return user['role'] if user else 'user'

    def set_user_role(self, telegram_id: int, role: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE users SET role=? WHERE telegram_id=?",
                (role, telegram_id)
            )

    def get_all_users(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_workers(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM users WHERE role='worker'"
            ).fetchall()
            return [dict(row) for row in rows]

    def remove_worker(self, telegram_id: int):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE users SET role='user' WHERE telegram_id=?",
                (telegram_id,)
            )

    def create_worker_password(self, password: str, created_by: int) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO worker_passwords (password, created_by) VALUES (?,?)",
                (password, created_by)
            )
            return cur.lastrowid

    def use_worker_password(self, password: str, telegram_id: int) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM worker_passwords WHERE password=? AND is_used=0",
                (password,)
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE worker_passwords SET is_used=1, used_by=? WHERE id=?",
                (telegram_id, row['id'])
            )
            conn.execute(
                "UPDATE users SET role='worker' WHERE telegram_id=?",
                (telegram_id,)
            )
            return True

    def get_worker_passwords(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT wp.*, u.full_name as used_by_name "
                "FROM worker_passwords wp "
                "LEFT JOIN users u ON wp.used_by = u.telegram_id "
                "ORDER BY wp.created_at DESC LIMIT 20"
            ).fetchall()
            return [dict(row) for row in rows]

    # ══════════════════════════════════════
    # SITE ADMIN PANEL (per-employee logins)
    # ══════════════════════════════════════
    def create_site_admin(self, username: str, password_hash: str,
                           full_name: str = "", role: str = "worker") -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO site_admins (username, password_hash, full_name, role) VALUES (?,?,?,?)",
                (username.strip(), password_hash, full_name, role)
            )
            return cur.lastrowid

    def username_exists(self, username: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM site_admins WHERE LOWER(username)=LOWER(?)",
                (username.strip(),)
            ).fetchone()
            return row is not None

    def get_site_admin_by_username(self, username: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM site_admins WHERE LOWER(username)=LOWER(?) AND is_active=1",
                (username.strip(),)
            ).fetchone()
            return dict(row) if row else None

    def get_site_admin(self, admin_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM site_admins WHERE id=?", (admin_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_site_admins(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, username, full_name, role, is_active, created_at "
                "FROM site_admins ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def deactivate_site_admin(self, admin_id: int):
        with self.get_connection() as conn:
            conn.execute("UPDATE site_admins SET is_active=0 WHERE id=?", (admin_id,))
            conn.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin_id,))

    def count_site_admins(self) -> int:
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM site_admins WHERE is_active=1").fetchone()
            return row['c'] if row else 0

    def create_session(self, token: str, admin_id: int):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO admin_sessions (token, admin_id) VALUES (?,?)",
                (token, admin_id)
            )

    def get_session_admin(self, token: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT sa.* FROM admin_sessions s "
                "JOIN site_admins sa ON s.admin_id = sa.id "
                "WHERE s.token=? AND sa.is_active=1",
                (token,)
            ).fetchone()
            return dict(row) if row else None

    def delete_session(self, token: str):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE token=?", (token,))

    def add_category(self, name: str, has_sizes: bool = False) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO categories (name, has_sizes) VALUES (?,?)",
                (name, 1 if has_sizes else 0)
            )
            return cur.lastrowid

    def update_category(self, cat_id: int, name: str = None, has_sizes: bool = None):
        fields, params = [], []
        if name is not None:
            fields.append("name=?"); params.append(name)
        if has_sizes is not None:
            fields.append("has_sizes=?"); params.append(1 if has_sizes else 0)
        if not fields:
            return
        params.append(cat_id)
        with self.get_connection() as conn:
            conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id=?", params)

    def get_categories(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
            return [dict(row) for row in rows]

    def get_category(self, cat_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
            return dict(row) if row else None

    def get_category_name(self, cat_id: int) -> str:
        cat = self.get_category(cat_id)
        return cat['name'] if cat else "Noma'lum"

    def category_has_sizes(self, cat_id: int) -> bool:
        cat = self.get_category(cat_id)
        return bool(cat['has_sizes']) if cat else False

    def delete_category(self, cat_id: int):
        with self.get_connection() as conn:
            conn.execute("UPDATE products SET is_active=0 WHERE category_id=?", (cat_id,))
            conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))

    def product_name_exists(self, name: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM products WHERE LOWER(name)=LOWER(?) AND is_active=1",
                (name.strip(),)
            ).fetchone()
            return row is not None

    def add_product(self, name: str, price: int, description: str,
                    category_id: int, photo_id: str = None,
                    photo_url: str = None, sizes: str = None) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO products (name, price, description, category_id, photo_id, photo_url, sizes) VALUES (?,?,?,?,?,?,?)",
                (name, price, description, category_id, photo_id, photo_url, sizes)
            )
            return cur.lastrowid

    def update_product_field(self, product_id: int, field: str, value):
        allowed = {'name', 'price', 'description', 'photo_id', 'photo_url', 'sizes', 'category_id'}
        if field not in allowed:
            return
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE products SET {field}=? WHERE id=?", (value, product_id)
            )

    def update_product(self, product_id: int, **fields):
        """Bir nechta maydonni bir yo'la yangilash (admin panel uchun)."""
        allowed = {'name', 'price', 'description', 'photo_id', 'photo_url', 'sizes', 'category_id'}
        set_parts, params = [], []
        for k, v in fields.items():
            if k in allowed:
                set_parts.append(f"{k}=?")
                params.append(v)
        if not set_parts:
            return
        params.append(product_id)
        with self.get_connection() as conn:
            conn.execute(f"UPDATE products SET {', '.join(set_parts)} WHERE id=?", params)

    def get_products_by_category(self, cat_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE category_id=? AND is_active=1 ORDER BY id",
                (cat_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_product(self, product_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT p.*, c.has_sizes FROM products p "
                "LEFT JOIN categories c ON p.category_id=c.id "
                "WHERE p.id=?", (product_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_products(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT p.*, c.name as cat_name, c.has_sizes FROM products p "
                "LEFT JOIN categories c ON p.category_id=c.id "
                "WHERE p.is_active=1 ORDER BY p.id"
            ).fetchall()
            return [dict(row) for row in rows]

    def search_products(self, query: str) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT p.*, c.name as cat_name, c.has_sizes FROM products p "
                "LEFT JOIN categories c ON p.category_id=c.id "
                "WHERE p.is_active=1 AND LOWER(p.name) LIKE LOWER(?) "
                "ORDER BY p.name LIMIT 20",
                (f"%{query.strip()}%",)
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_product(self, product_id: int):
        with self.get_connection() as conn:
            conn.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))

    def add_to_cart(self, user_id: int, product_id: int, size: str = None):
        with self.get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM cart WHERE user_id=? AND product_id=? AND size IS ?",
                (user_id, product_id, size)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE cart SET quantity=quantity+1 WHERE id=?", (existing['id'],)
                )
            else:
                conn.execute(
                    "INSERT INTO cart (user_id, product_id, quantity, size) VALUES (?,?,1,?)",
                    (user_id, product_id, size)
                )

    def get_cart(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT c.id as cart_id, c.product_id, c.quantity, c.size, "
                "p.name, p.price, p.photo_id "
                "FROM cart c JOIN products p ON c.product_id=p.id "
                "WHERE c.user_id=?",
                (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def remove_from_cart(self, cart_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM cart WHERE id=?", (cart_id,))

    def clear_cart(self, user_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))

    def create_order(self, user_id: int, customer_name: str, phone: str,
                     address: str, payment: str, items: List[Dict],
                     total: int, discount_pct: int = 0, discount_amt: int = 0,
                     delivery: str = None) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO orders (user_id, customer_name, phone, address, payment, "
                "delivery, total, discount_pct, discount_amt) VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, customer_name, phone, address, payment,
                 delivery, total, discount_pct, discount_amt)
            )
            order_id = cur.lastrowid
            for item in items:
                conn.execute(
                    "INSERT INTO order_items (order_id, product_id, product_name, "
                    "price, quantity, size) VALUES (?,?,?,?,?,?)",
                    (order_id, item['product_id'], item['name'],
                     item['price'], item['quantity'], item.get('size'))
                )
            return order_id

    def get_order(self, order_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            return dict(row) if row else None

    def get_order_items(self, order_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM order_items WHERE order_id=?", (order_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_user_orders(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_all_orders(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            return [dict(row) for row in rows]

    def update_order_status(self, order_id: int, status: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE orders SET status=? WHERE id=?", (status, order_id)
            )
