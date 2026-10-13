"""Current frontend's named result command, implemented solely by this new skill."""
import argparse
import json
from pathlib import Path
import sys
from paper import publish

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', '--workspace', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(publish(Path(args.workdir).resolve()), ensure_ascii=False))
    except (ValueError, OSError, KeyError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
