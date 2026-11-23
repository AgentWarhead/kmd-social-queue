#!/bin/bash
# Vercel's skip check for the timer: exit 0 skips the build, exit 1 builds.
# Build on the first deploy and whenever timer/ changed. Vercel clones only
# a few commits deep, so when the last deployed commit is out of reach the
# check compares against the commit before this one.
if [ -z "$VERCEL_GIT_PREVIOUS_SHA" ]; then exit 1; fi
if git cat-file -e "$VERCEL_GIT_PREVIOUS_SHA^{commit}" 2>/dev/null; then
  base="$VERCEL_GIT_PREVIOUS_SHA"
else
  base="HEAD^"
fi
if git diff --quiet "$base" HEAD -- .; then exit 0; fi
exit 1
