import os
import sys
import time
from datetime import datetime
import pandas as pd

# test_agent.py lives in tests/, but agent.py lives one directory up in the
# project root -- Python only puts this script's own directory on sys.path,
# so the plain "from agent import ..." below would fail with
# ModuleNotFoundError no matter how this file is invoked. Add the project
# root explicitly before importing.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import app, MAX_ATTEMPTS

TEST_CASES=[
    {'difficulty': 'easy',
     'question':"how many questions were posted in 2023"},
    {'difficulty': 'easy',
     'question':"how many upvotes were casted in 2022?"},
    {'difficulty': 'medium',
     'question':"which posts are marked as duplicates of another post ?"},
    {'difficulty': 'medium',
     'question':"users with over 1000 reputation who have never had a post recieve  a deletion vote "},
    {'difficulty': 'hard',
     'question':"what is the most upvoted answer to the highest view count question ?"},
    {'difficulty': 'hard',
     'question':"which users earned more than 3 badges within thier first year on site ?"},
    {'difficulty': 'ambigous',
     'question':"who are the best users"},
    {'difficulty': 'stress',
     'question':"top 5 users by reputation who answered questiions about python ?"},
    {'difficulty': 'stress',
     'question':"for each tag ,what is the average reputation of users who answered questions with that tag?"},
]

def make_initial_state(question: str)-> dict:
    return{
        'question':question,
                'sql':None,
                'validated_sql': None,
                'result': None,
                "error": None,
                'attempts': 0,
    }
    
def run_case(case: dict, thread_id: str)-> dict:
    print (f"[{case['difficulty']}] running: {case['question']!r} ...")
    start= time.perf_counter()
    try:
        config = {"configurable": {"thread_id": thread_id}}
        final_state = app.invoke(make_initial_state(case["question"]), config=config)
        elapsed = time.perf_counter() - start
        success = final_state["result"] is not None

        row = {
            "difficulty": case["difficulty"],
            "question": case["question"],
            "success": success,
            "attempts": final_state["attempts"],
            "latency_s": round(elapsed, 2),
            "rows_returned": len(final_state["result"]["rows"]) if success else None,
            "error": final_state["error"] if not success else None,
        }

    except Exception as e:   # catches anything NOT handled inside the graph itself — a real crash, not a modeled failure
        elapsed = time.perf_counter() - start
        row = {
            "difficulty": case["difficulty"],
            "question": case["question"],
            "success": False,
            "attempts": None,
            "latency_s": round(elapsed, 2),
            "rows_returned": None,
            "error": f"unhandled exception: {e}",
        }

    print(f"  -> {'OK' if row['success'] else 'FAILED'} in {row['latency_s']}s, attempts={row['attempts']}")
    return row


def run_all() -> pd.DataFrame:
    # each case gets its own thread_id so unrelated test questions don't
    # bleed into each other's conversational history
    results = [
        run_case(c, thread_id=f"eval-{i}-{c['difficulty']}")
        for i, c in enumerate(TEST_CASES)
    ]
    df = pd.DataFrame(results)

    print("\n=== Full results ===")
    print(df.to_string(index=False))

    print("\n=== Summary by difficulty ===")
    summary = df.groupby("difficulty").agg(
        success_rate=("success", "mean"),
        avg_latency_s=("latency_s", "mean"),
        avg_attempts=("attempts", "mean"),
    )
    print(summary)

    # persist so this can feed the "AI Evaluation" section of PROJECT_PROGRESS.md
    # instead of hand-computing those numbers each time
    out_path = f"eval_results_{datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    return df


if __name__ == "__main__":
    run_all()