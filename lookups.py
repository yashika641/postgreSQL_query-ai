# Stack Overflow encodes several columns as opaque integer/bit codes with no
# lookup table in the database itself (they're documented only in SO's
# external schema docs). Reflection and relationships.py can't recover this
# meaning, but the LLM needs it to generate correct WHERE clauses
# (e.g. "questions" -> posttypeid = 1, not a guess).

LOOKUPS = {
    "posts": {
        "posttypeid": {
            1: "Question",
            2: "Answer",
            3: "Orphaned TagWiki",
            4: "TagWikiExcerpt",
            5: "TagWiki",
            6: "ModeratorNomination",
            7: "WikiPlaceholder",
            8: "PrivilegeWiki",
        },
    },
    "votes": {
        "votetypeid": {
            1: "AcceptedByOriginator",
            2: "UpMod",
            3: "DownMod",
            4: "Offensive",
            5: "Favorite",
            6: "Close",
            7: "Reopen",
            8: "BountyStart",
            9: "BountyClose",
            10: "Deletion",
            11: "Undeletion",
            12: "Spam",
            13: "InformModerator",
        },
    },
    "postlinks": {
        "linktypeid": {
            1: "Linked",
            3: "Duplicate",
        },
    },
}
