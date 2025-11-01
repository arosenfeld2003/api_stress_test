from flask import Blueprint, request, jsonify
import uuid
from src.db.connection import get_connection
from src.db.warrior import (
    create_warrior,
    get_warrior,
    search_warriors,
    count_warriors,
)

warrior_bp = Blueprint('warrior', __name__)


@warrior_bp.route('/warrior', methods=['POST'])
def create_warrior_endpoint():
    """Create a new warrior. Returns 201 with Location header."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify(error="Request body must be JSON"), 400
        
        # Validate required fields
        name = data.get('name')
        dob = data.get('dob')
        fight_skills = data.get('fight_skills')
        
        if not name:
            return jsonify(error="Field 'name' is required"), 400
        if not dob:
            return jsonify(error="Field 'dob' is required"), 400
        if not fight_skills:
            return jsonify(error="Field 'fight_skills' is required"), 400
        if not isinstance(fight_skills, list):
            return jsonify(error="Field 'fight_skills' must be a list"), 400
        
        # Generate UUID v4
        warrior_id = str(uuid.uuid4())
        
        # Insert warrior into database
        with get_connection(read_only=False) as con:
            create_warrior(
                con,
                id=warrior_id,
                name=name,
                dob=dob,
                fight_skills=fight_skills,
            )
        
        # Return 201 with Location header
        response = jsonify({
            "id": warrior_id,
            "name": name,
            "dob": dob,
            "fight_skills": fight_skills,
        })
        response.status_code = 201
        response.headers['Location'] = f'/warrior/{warrior_id}'
        return response
        
    except Exception as e:
        return jsonify(error=str(e)), 500


@warrior_bp.route('/warrior/<id>', methods=['GET'])
def get_warrior_endpoint(id):
    """Get warrior by ID. Returns 200 or 404."""
    try:
        with get_connection(read_only=True) as con:
            warrior = get_warrior(con, id=id)
        
        if warrior is None:
            return jsonify(error="Warrior not found"), 404
        
        return jsonify(warrior), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500


@warrior_bp.route('/warrior', methods=['GET'])
def search_warrior_endpoint():
    """Search warriors by term. Returns 200 with results or 400 if no term."""
    search_term = request.args.get('t')
    
    if not search_term:
        return jsonify(error="Query parameter 't' (search term) is required"), 400
    
    try:
        with get_connection(read_only=True) as con:
            warriors = search_warriors(con, term=search_term, limit=50)
        
        return jsonify(warriors), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500


@warrior_bp.route('/counting-warriors', methods=['GET'])
def count_warrior_endpoint():
    """Count all registered warriors. Returns 200 with count."""
    try:
        with get_connection(read_only=True) as con:
            count = count_warriors(con)
        
        return jsonify(count=count), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500

