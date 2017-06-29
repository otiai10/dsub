# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Setup module for end-to-end dsub tests."""

# pylint: disable=line-too-long
# test_setup_e2e.py
#
# Intended to be imported into a test.
# Automatically imports variables from test_setup.py
#
# * Automatically determine PROJECT_ID
# * Automatically pick up a bucket name for tests.
#
# * Automatically set environment variables:
#   * LOGGING=gs://${DSUB_BUCKET}/dsub/py/${DSUB_PROVIDER}/${TEST_NAME}/logging/
#     (task file tests)
#   * LOGGING=gs://${DSUB_BUCKET}/dsub/py/${DSUB_PROVIDER}/${TEST_NAME}/logging/${TEST_NAME}.log
#     (non-task file tests)
#   * INPUTS=gs://${DSUB_BUCKET}/dsub/py/${DSUB_PROVIDER}/${TEST_NAME}/input
#   * OUTPUTS=gs://${DSUB_BUCKET}/dsub/py/${DSUB_PROVIDER}/${TEST_NAME}/output
#
# * Check if LOGGING, INPUTS, and OUTPUTS are empty.
# * For task file tests, generate the file from TASKS_FILE_TMPL.
# pylint: enable=line-too-long

import os
import subprocess
import sys

from dsub.commands import dsub as dsub_command

import test_setup
import test_util

TEST_VARS = ("TEST_NAME", "TEST_DIR", "TEST_TMP", "TASKS_FILE",
             "TASKS_FILE_TMPL",)
TEST_E2E_VARS = ("PROJECT_ID", "DSUB_BUCKET", "LOGGING", "INPUTS", "OUTPUTS",
                 "DOCKER_INPUTS", "DOCKER_OUTPUTS",)


def _environ():
  """Merge the current enviornment and test variables into a dictionary."""
  e = dict(os.environ)
  for var in TEST_VARS + TEST_E2E_VARS:
    e[var] = globals()[var]

  return e


# Copy test_setup variables
TEST_NAME = test_setup.TEST_NAME
TEST_DIR = test_setup.TEST_DIR
TEST_TMP = test_setup.TEST_TMP
TASKS_FILE = test_setup.TASKS_FILE
TASKS_FILE_TMPL = test_setup.TASKS_FILE_TMPL

print "Checking that required environment values are set:"

DSUB_PROVIDER = os.getenv("DSUB_PROVIDER", "google")

if "YOUR_PROJECT" in os.environ:
  PROJECT_ID = os.environ["YOUR_PROJECT"]
else:
  print "Checking configured gcloud project"
  PROJECT_ID = subprocess.check_output(
      'gcloud config list core/project --format="value(core.project)"',
      shell=True).strip()

if not PROJECT_ID:
  print "Your project ID could not be determined."
  print "Set the environment variable YOUR_PROJECT or run \"gcloud init\"."
  sys.exit(1)

print "  Project ID detected as: %s" % PROJECT_ID

if "YOUR_BUCKET" in os.environ:
  DSUB_BUCKET = os.environ["YOUR_BUCKET"]
else:
  DSUB_BUCKET = "%s-dsub-test" % os.environ["USER"]

print "  Bucket detected as: %s" % DSUB_BUCKET

print "  Checking if bucket exists"
if not test_util.gsutil_ls_check("gs://%s" % DSUB_BUCKET):
  print >> sys.stderr, "Bucket does not exist: %s" % DSUB_BUCKET
  print >> sys.stderr, "Create the bucket with \"gsutil mb\"."
  sys.exit(1)

# Set standard LOGGING, INPUTS, and OUTPUTS values
TEST_REMOTE_ROOT = "gs://%s/dsub/py/%s/%s" % (DSUB_BUCKET, DSUB_PROVIDER,
                                              TEST_NAME)
TEST_DOCKER_ROOT = "gs/%s/dsub/py/%s/%s" % (DSUB_BUCKET, DSUB_PROVIDER,
                                            TEST_NAME)

if TASKS_FILE:
  # For task file tests, the logging path is a directory.
  # Eventually each job should have its own sub-directory,
  # and named logging files but we need to add dsub support for that.
  LOGGING = "%s/logging" % TEST_REMOTE_ROOT
else:
  # For regular tests, the logging path is a named file.
  LOGGING = TEST_REMOTE_ROOT + "/%s/logging/%s.log" % (TEST_NAME, TEST_NAME)
  STDOUT_LOG = "%s/%s-stdout.log" % (os.path.dirname(LOGGING), TEST_NAME)
  STDERR_LOG = "%s/%s-stderr.log" % (os.path.dirname(LOGGING), TEST_NAME)

INPUTS = "%s/input" % TEST_REMOTE_ROOT
OUTPUTS = "%s/output" % TEST_REMOTE_ROOT
DOCKER_INPUTS = "%s/input" % TEST_DOCKER_ROOT
DOCKER_OUTPUTS = "%s/output" % TEST_DOCKER_ROOT

print "Logging path: %s" % LOGGING
print "Input path: %s" % INPUTS
print "Output path: %s" % OUTPUTS

if not os.environ.get("CHECK_RESULTS_ONLY"):

  print "  Checking if remote test files already exists"
  if test_util.gsutil_ls_check("%s/**" % TEST_REMOTE_ROOT):
    print >> sys.stderr, "Test files exist: %s" % TEST_REMOTE_ROOT
    print >> sys.stderr, "Remove contents:"
    print >> sys.stderr, "  gsutil -m rm %s/**" % os.path.dirname(
        TEST_REMOTE_ROOT)
    sys.exit(1)

if TASKS_FILE:
  # For a task file test, set up the task file from its template
  # This should really be a feature of dsub directly...
  print "Setting up task file %s" % TASKS_FILE
  os.makedirs(os.path.dirname(TASKS_FILE))
  test_util.expand_tsv_fields(_environ(), TASKS_FILE_TMPL, TASKS_FILE)


# Functions for launching dsub
#
# Tests should generally just call "run_dsub" which will then invoke
# the provider-specific function.


def run_dsub(dsub_args):
  # Execute the appropriate dsub_<provider> function
  return globals()["dsub_%s" % DSUB_PROVIDER](dsub_args)


def dsub_google(dsub_args):
  """Call dsub appending google-provider required arguments."""
  # pyformat: disable
  google_opt_args = [
      ("BOOT_DISK_SIZE", "--boot-disk-size"),
      ("DISK_SIZE", "--disk-size")
  ]
  # pyformat: enable

  opt_args = []
  for var in google_opt_args:
    val = globals().get(var[0])
    if val:
      opt_args.append(var[1], val)

  # pyformat: disable
  return dsub_command.call([
      "--provider", "google",
      "--project", PROJECT_ID,
      "--logging", LOGGING,
      "--zones", "us-central1-*"
      ] + opt_args + dsub_args)
  # pyformat: enable


def dsub_local(dsub_args):
  """Call dsub appending local-provider required arguments."""

  # pyformat: disable
  return dsub_command.call([
      "--provider", "local",
      "--logging", LOGGING,
      ] + dsub_args)
