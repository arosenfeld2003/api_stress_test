from flask import Blueprint, request, jsonify
import uuid
import time
import logging
from src.db.connection import get_connection
from src.db.pool import get_pooled_connection
import os
from src.db.warrior import (
    create_warrior,
    get_warrior,
    search_warriors,
    count_warriors,
)

warrior_bp = Blueprint('warrior', __name__)
logger = logging.getLogger(__name__)


@warrior_bp.route('/warrior', methods=['POST'])
def create_warrior_endpoint():
    """Create a new warrior. Returns 201 with Location header."""
    start_time = time.time()
    try:
        data = request.get_json()
        
        if not data:
            return jsonify(error="Request body must be JSON"), 400
        
        # Validate required fields
        name = data.get('name')
        dob = data.get('dob')
        fight_skills = data.get('fight_skills')
        
        # Track validation errors for proper 422 response
        validation_errors = []
        
        if not name:
            validation_errors.append("Field 'name' is required")
        elif not isinstance(name, str):
            validation_errors.append("Field 'name' must be a string")
        elif len(name) > 100:
            validation_errors.append("Field 'name' must be 100 characters or less")
        
        if not dob:
            validation_errors.append("Field 'dob' is required")
        elif not isinstance(dob, str):
            validation_errors.append("Field 'dob' must be a string")
        else:
            # Validate date format (YYYY-MM-DD)
            try:
                from datetime import datetime
                datetime.strptime(dob, '%Y-%m-%d')
            except ValueError:
                validation_errors.append("Field 'dob' must be in YYYY-MM-DD format")
        
        if fight_skills is None:
            validation_errors.append("Field 'fight_skills' is required")
        elif not isinstance(fight_skills, list):
            validation_errors.append("Field 'fight_skills' must be a list")
        elif len(fight_skills) == 0:
            validation_errors.append("Field 'fight_skills' must contain at least one skill")
        else:
            # Validate each skill is a string
            for skill in fight_skills:
                if not isinstance(skill, str):
                    validation_errors.append("All items in 'fight_skills' must be strings")
                    break
        
        # Return 422 for validation errors (as expected by stress test)
        if validation_errors:
            return jsonify(error="Validation failed", details=validation_errors), 422
        
        # Generate UUID v4
        warrior_id = str(uuid.uuid4())
        
        # Insert warrior into database using connection pool for better performance
        use_pool = os.getenv('USE_DB_POOL', 'true').lower() == 'true'
        
        if use_pool:
            with get_pooled_connection() as con:
                create_warrior(
                    con,
                    id=warrior_id,
                    name=name,
                    dob=dob,
                    fight_skills=fight_skills,
                )
        else:
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
        
        # Log performance metrics
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"POST /warrior completed in {elapsed:.2f}ms")
        return response
        
    except Exception as e:
        # Log the error for debugging
        import traceback
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"Error creating warrior after {elapsed:.2f}ms: {e}\n{traceback.format_exc()}")
        return jsonify(error=str(e)), 500


@warrior_bp.route('/warrior/<id>', methods=['GET'])
def get_warrior_endpoint(id):
    """Get warrior by ID. Returns 200 or 404."""
    try:
        use_pool = os.getenv('USE_DB_POOL', 'true').lower() == 'true'
        
        if use_pool:
            with get_pooled_connection() as con:
                warrior = get_warrior(con, id=id)
        else:
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
        use_pool = os.getenv('USE_DB_POOL', 'true').lower() == 'true'
        
        if use_pool:
            with get_pooled_connection() as con:
                warriors = search_warriors(con, term=search_term, limit=50)
        else:
            with get_connection(read_only=True) as con:
                warriors = search_warriors(con, term=search_term, limit=50)
        
        return jsonify(warriors), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500


@warrior_bp.route('/counting-warriors', methods=['GET'])
def count_warrior_endpoint():
    """Count all registered warriors. Returns 200 with count."""
    try:
        use_pool = os.getenv('USE_DB_POOL', 'true').lower() == 'true'
        
        if use_pool:
            with get_pooled_connection() as con:
                count = count_warriors(con)
        else:
            with get_connection(read_only=True) as con:
                count = count_warriors(con)
        
        return jsonify(count=count), 200
        
    except Exception as e:
        return jsonify(error=str(e)), 500

