from flask import Flask, request, jsonify
from src.services.amadeus_service import AmadeusService
from src.services.flight_service import FlightService
from src.services.ynab_service import YNABService
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize services
amadeus_service = AmadeusService()
flight_service = FlightService()
ynab_service = YNABService()

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"})

# Amadeus Service Endpoints
@app.route('/api/iata-code', methods=['GET'])
def get_iata_code():
    """Get IATA code for a location"""
    location = request.args.get('location')
    if not location:
        return jsonify({"success": False, "message": "Location parameter is required"}), 400
    
    iata_code = amadeus_service.get_iata_code(location)
    if iata_code:
        return jsonify({"success": True, "data": {"location": location, "iata_code": iata_code}})
    else:
        return jsonify({"success": False, "message": f"Could not find IATA code for {location}"}), 404

# Flight Service Endpoints
@app.route('/api/search-flights', methods=['GET'])
def search_flights():
    """Search for flights based on parameters"""
    departure = request.args.get('departure')
    destination = request.args.get('destination')
    duration = request.args.get('duration')
    max_price = request.args.get('max_price')
    one_way = request.args.get('one_way', 'false').lower() == 'true'
    departure_date = request.args.get('departure_date')
    
    if not departure:
        return jsonify({"success": False, "message": "Departure parameter is required"}), 400
    
    result = flight_service.search_flights(
        departure=departure,
        destination=destination,
        duration=duration,
        max_price=max_price,
        one_way=one_way,
        departure_date=departure_date
    )
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 404

@app.route('/api/flight-offers', methods=['GET'])
def get_flight_offers():
    """Get flight offers based on parameters"""
    departure = request.args.get('departure')
    destination = request.args.get('destination')
    departure_date = request.args.get('departure_date')
    num_adults = request.args.get('num_adults', '1')
    return_date = request.args.get('return_date')
    num_children = request.args.get('num_children')
    num_infants = request.args.get('num_infants')
    travel_class = request.args.get('travel_class')
    one_way = request.args.get('one_way', 'false').lower() == 'true'
    max_price = request.args.get('max_price')
    
    if not departure or not destination or not departure_date:
        return jsonify({
            "success": False, 
            "message": "Departure, destination, and departure_date parameters are required"
        }), 400
    
    result = flight_service.get_flight_offers(
        departure=departure,
        destination=destination,
        departure_date=departure_date,
        num_adults=num_adults,
        return_date=return_date,
        num_children=num_children,
        num_infants=num_infants,
        travel_class=travel_class,
        one_way=one_way,
        max_price=max_price
    )
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 404

# YNAB Service Endpoints
@app.route('/api/travel-budget', methods=['GET'])
def get_travel_budget():
    """Get travel budget information from YNAB"""
    budget_info = ynab_service.get_travel_budget()
    
    if budget_info:
        return jsonify({
            "success": True,
            "data": {"budget": budget_info}
        })
    else:
        return jsonify({
            "success": False,
            "message": "Could not retrieve travel budget information"
        }), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
