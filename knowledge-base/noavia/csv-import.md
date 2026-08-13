# Importing ticket data from CSV

Administrators can import historical tickets from a UTF-8 CSV file. Required
columns are `subject`, `description`, and `created_at`; optional columns
include `requester_email`, `status`, and `priority`.

The importer validates each row before creating tickets. Rows with an invalid
date or a missing required value are reported in a downloadable error file;
valid rows still import. Duplicate external IDs are skipped.

Remove unnecessary personal data before upload. CSV imports are intended for
historical migration, not a live ticket feed.
