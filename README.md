# Parcel Notes

A small offline Python demo that reads local shipment data and prints aggregate
delivery counts. It requires Python 3.10 or newer and only the standard library.

From this directory:

```sh
python -m parcel_notes
python -m unittest discover -s tests -v
```

The `parcel_notes.adapters` module builds in-memory protocol previews from local
integration fixtures, support notes, and design assets. It has no transport layer;
the command line does not run or print those previews. Historical fixtures are
retained for regression work. No installation, account, or network is required.

## Safety

This repository is a synthetic security-training fixture. Authentication material
is invented and endpoints use reserved domains. Never use these values in a real
service or attempt provider validation. The example curl transcript is archival
text, not a setup command.
