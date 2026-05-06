from flask import Blueprint, jsonify
from strategies.signal_aggregator import get_aggregated_signal

signals_bp = Blueprint("signals", __name__)


@signals_bp.route("/signals/<symbol>")
def signals(symbol):

    # Normalize symbol to uppercase for consistency
    symbol = symbol.upper()

    # Call signal aggregation logic
    result = get_aggregated_signal(symbol)

    # Handle case where no signal could be generated
    if result is None:
        return jsonify({
            "error": f"Could not generate signals for '{symbol}'"
        }), 404

    # Add symbol to response for clarity in API output
    result["symbol"] = symbol

    return jsonify(result), 200
