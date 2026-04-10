import os
import timeit
import unittest.mock
os.environ['JULES_API_KEY'] = 'test_key'
import main

# Generate huge payload to really see a difference
unidiff = """--- a/file1.txt
+++ b/file1.txt
@@ -1,2 +1,3 @@
 line 1
+line 2
"""
for i in range(100):
    unidiff += f"+++ b/file{i}.txt\n"
    for j in range(100):
        unidiff += f" line {j}\n+ added {j}\n- removed {j}\n"

activity = {
    "artifacts": [
        {
            "changeSet": {
                "gitPatch": {
                    "unidiffPatch": unidiff
                }
            }
        }
    ]
}

def run_parse():
    # we need to redirect stdout to null or it prints too much
    import sys, io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    main.parse_activity(activity)
    sys.stdout = old_stdout

print("Original baseline for 30k lines diff:")
print(timeit.timeit(run_parse, number=100))
