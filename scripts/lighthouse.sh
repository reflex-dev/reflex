#!/bin/bash

# Change directory to the first argument passed to the script
project_dir=$1
shift
pushd "$project_dir" || exit 1
echo "Changed directory to $project_dir"

cat << EOF > lighthouserc.js
module.exports = {
  ci: {
    collect: {
     staticDistDir: './public',
     numberOfRuns: 1,
     url: ['http://localhost:3000']
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
};
EOF