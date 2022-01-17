#!/bin/bash
shopt -s nullglob
for f in $(find . -name '*.yaml'); do
    if cfn_nag_scan --input-path "$f" --blacklist-path ./codebuild/ValidateTemplates/blacklist-cfnnag.yml; then
        echo "$f PASSED"
    else
        echo "$f FAILED" | tee -a failed_scripts.txt
        touch FAILED
    fi
done

if [ -e FAILED ]; then
  echo cfn-nag FAILED for the following files:
  cat failed_scripts.txt
  exit 1
else
  echo cfn-nag PASSED on all files!
  exit 0
fi
