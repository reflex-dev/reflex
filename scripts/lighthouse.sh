#!/bin/bash

cat << EOF > lighthouserc.js
module.exports = {
  ci: {
    collect: {
     staticDistDir: './public',
     numberOfRuns: 1
    },
    upload: {
      /* Add configuration here */
    },
  },
};
EOF