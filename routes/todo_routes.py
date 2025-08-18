"""
Todo routes for task management
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

todo_bp = Blueprint('todo', __name__)


@todo_bp.route('/todos')
@login_required
def list_todos():
    """List all todos for the current user"""
    todo_service = current_app.services.get('todo')
    todos = todo_service.get_user_todos(current_user.id)
    return render_template('todos/list.html', todos=todos)


@todo_bp.route('/api/todos')
@login_required
def api_list_todos():
    """API endpoint to get todos"""
    todo_service = current_app.services.get('todo')
    todos = todo_service.get_user_todos(current_user.id)
    
    return jsonify({
        'todos': [todo_service.serialize_todo(todo) for todo in todos]
    })


@todo_bp.route('/api/todos', methods=['POST'])
@login_required
def api_create_todo():
    """API endpoint to create a new todo"""
    data = request.get_json()
    
    try:
        todo_service = current_app.services.get('todo')
        todo = todo_service.create_todo(current_user.id, data)
        
        return jsonify({
            'success': True,
            'todo': todo_service.serialize_todo(todo)
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to create todo'}), 500


@todo_bp.route('/api/todos/<int:todo_id>', methods=['PUT'])
@login_required
def api_update_todo(todo_id):
    """API endpoint to update a todo"""
    data = request.get_json()
    
    try:
        todo_service = current_app.services.get('todo')
        todo = todo_service.update_todo(todo_id, current_user.id, data)
        
        if not todo:
            return jsonify({'error': 'Todo not found'}), 404
        
        return jsonify({
            'success': True,
            'todo': todo_service.serialize_todo(todo)
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to update todo'}), 500


@todo_bp.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@login_required
def api_toggle_todo(todo_id):
    """API endpoint to toggle todo completion status"""
    try:
        todo_service = current_app.services.get('todo')
        todo = todo_service.toggle_todo_completion(todo_id, current_user.id)
        
        if not todo:
            return jsonify({'error': 'Todo not found'}), 404
        
        return jsonify({
            'success': True,
            'is_completed': todo.is_completed,
            'completed_at': todo.completed_at.isoformat() if todo.completed_at else None
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to toggle todo'}), 500


@todo_bp.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def api_delete_todo(todo_id):
    """API endpoint to delete a todo"""
    try:
        todo_service = current_app.services.get('todo')
        success = todo_service.delete_todo(todo_id, current_user.id)
        
        if not success:
            return jsonify({'error': 'Todo not found'}), 404
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': 'Failed to delete todo'}), 500


@todo_bp.route('/api/todos/dashboard')
@login_required
def api_dashboard_todos():
    """API endpoint to get todos for dashboard widget"""
    try:
        todo_service = current_app.services.get('todo')
        result = todo_service.get_dashboard_todos(current_user.id, limit=5)
        
        return jsonify({
            'todos': [
                {
                    'id': todo.id,
                    'title': todo.title,
                    'priority': todo.priority,
                    'due_date': todo.due_date.isoformat() if todo.due_date else None,
                    'created_at': todo.created_at.isoformat()
                } for todo in result['todos']
            ],
            'pending_count': result['pending_count']
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch dashboard todos'}), 500


@todo_bp.route('/api/todos/stats')
@login_required
def api_todo_stats():
    """API endpoint to get todo statistics"""
    try:
        todo_service = current_app.services.get('todo')
        stats = todo_service.get_todo_stats(current_user.id)
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch todo stats'}), 500