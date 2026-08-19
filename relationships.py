# Stack Overflow's public dump doesn't declare real FK constraints, so these
# are hand-encoded from the schema documented in db.txt. Used to give the
# LLM join guidance in Phase 4 that reflection alone can't provide.

RELATIONSHIPS = [
    {"from_table": "posts", "from_column": "owneruserid", "to_table": "users", "to_column": "id"},
    {"from_table": "posts", "from_column": "lasteditoruserid", "to_table": "users", "to_column": "id"},
    {"from_table": "posts", "from_column": "acceptedanswerid", "to_table": "posts", "to_column": "id"},
    {"from_table": "posts", "from_column": "parentid", "to_table": "posts", "to_column": "id"},
    {"from_table": "comments", "from_column": "postid", "to_table": "posts", "to_column": "id"},
    {"from_table": "comments", "from_column": "userid", "to_table": "users", "to_column": "id"},
    {"from_table": "badges", "from_column": "userid", "to_table": "users", "to_column": "id"},
    {"from_table": "votes", "from_column": "postid", "to_table": "posts", "to_column": "id"},
    {"from_table": "votes", "from_column": "userid", "to_table": "users", "to_column": "id"},
    {"from_table": "postlinks", "from_column": "postid", "to_table": "posts", "to_column": "id"},
    {"from_table": "postlinks", "from_column": "relatedpostid", "to_table": "posts", "to_column": "id"},
    {"from_table": "tags", "from_column": "excerptpostid", "to_table": "posts", "to_column": "id"},
    {"from_table": "tags", "from_column": "wikipostid", "to_table": "posts", "to_column": "id"},
    {"from_table": "post_tags", "from_column": "post_id", "to_table": "posts", "to_column": "id"},
]
