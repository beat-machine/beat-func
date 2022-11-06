# beat-func

The backend for https://github.com/beat-machine/beat-webapp.

`beatfunc.core` defines the main API operations without actually implementing a server. You can use its definitions to
create a service for your cloud platform/environment of choice.

`beatfunc.simple` is a rudimentary HTTP API. It does jobs as very long POST requests. It also leaves a lot of garbage
behind because it expects to be used with Google Cloud Run, where it would constantly be destroyed and recreated. This
is the backend used by beat-webapp, which will hopefully be replaced by something more sane someday.
