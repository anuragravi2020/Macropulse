# Author: Kevin Ngo, 4/18/26
# Search route for the API, including query validation and error handling.
from flask import Blueprint, request, jsonify
from services.data_fetcher import search_stocks

# Kevin Ngo, 4/18/26
# Blueprint registration for the search endpoint.
search_bp = Blueprint("search", __name__)


# Kevin Ngo, 4/18/26
# Helper to return standardized error JSON payloads.
def _error_response(message, status=400):
    return jsonify({
        "results": [],
        "error": message,
    }), status


@search_bp.route("/search", methods=["GET"])
# Kevin Ngo, 4/18/26
# Search endpoint implementation.
def search():
    # Kevin Ngo, 4/18/26
    # Read the raw query parameter from the request.
    raw_query = request.args.get("q")

    if raw_query is None:
        # Kevin Ngo, 4/18/26
        # Reject requests with no query parameter.
        return _error_response("Missing required query parameter 'q'")

    # Kevin Ngo, 4/18/26
    # Trim whitespace from the query and validate it.
    query = raw_query.strip()
    if not query:
        # Kevin Ngo, 4/18/26
        # Reject empty or whitespace-only queries.
        return _error_response("Query parameter 'q' cannot be empty or whitespace")

    if len(query) < 2:
        # Kevin Ngo, 4/18/26
        # Enforce a minimum query length to avoid too broad searches.
        return _error_response("Query parameter 'q' must be at least 2 characters")

    if len(query) > 64:
        # Kevin Ngo, 4/18/26
        # Prevent excessively long queries.
        return _error_response("Query parameter 'q' cannot exceed 64 characters")

    try:
        # Kevin Ngo, 4/18/26
        # Perform the actual stock search.
        results = search_stocks(query)
    except Exception:
        # Kevin Ngo, 4/18/26
        # Handle unexpected backend failures gracefully.
        return _error_response("Unable to perform search at this time", 500)

    if not isinstance(results, list):
        # Kevin Ngo, 4/18/26
        # Ensure the response payload always includes a results list.
        results = []

    # Kevin Ngo, 4/18/26
    # Return the successful search payload.
    return jsonify({
        "query": query,
        "count": len(results),
        "results": results,
    }), 200
