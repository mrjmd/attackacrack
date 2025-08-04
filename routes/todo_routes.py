"""
Todo routes for task management
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from crm_database import Todo
from datetime import datetime

todo_bp = Blueprint('todo', __name__)


@todo_bp.route('/todos')
@login_required
def list_todos():
    """List all todos for the current user"""
    todos = Todo.query.filter_by(user_id=current_user.id).order_by(
        Todo.is_completed.asc(),
        Todo.created_at.desc()
    ).all()
    
    return render_template('todos/list.html', todos=todos)


@todo_bp.route('/api/todos')
@login_required
def api_list_todos():
    """API endpoint to get todos"""
    todos = Todo.query.filter_by(user_id=current_user.id).order_by(
        Todo.is_completed.asc(),
        Todo.created_at.desc()
    ).all()
    
    return jsonify({
        'todos': [{
            'id': todo.id,
            'title': todo.title,
            'description': todo.description,
            'is_completed': todo.is_completed,
            'priority': todo.priority,
            'due_date': todo.due_date.isoformat() if todo.due_date else None,
            'created_at': todo.created_at.isoformat(),
            'updated_at': todo.updated_at.isoformat() if todo.updated_at else None,
            'completed_at': todo.completed_at.isoformat() if todo.completed_at else None
        } for todo in todos]
    })


@todo_bp.route('/api/todos', methods=['POST'])
@login_required
def api_create_todo():
    """API endpoint to create a new todo"""
    data = request.get_json()
    
    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
    
    todo = Todo(
        title=data['title'],
        description=data.get('description', ''),
        priority=data.get('priority', 'medium'),
        user_id=current_user.id
    )
    
    if data.get('due_date'):
        try:
            todo.due_date = datetime.fromisoformat(data['due_date'])
        except ValueError:
            return jsonify({'error': 'Invalid due date format'}), 400
    
    db.session.add(todo)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'todo': {
            'id': todo.id,
            'title': todo.title,
            'description': todo.description,
            'is_completed': todo.is_completed,
            'priority': todo.priority,
            'created_at': todo.created_at.isoformat()
        }
    }), 201


@todo_bp.route('/api/todos/<int:todo_id>', methods=['PUT'])
@login_required
def api_update_todo(todo_id):
    """API endpoint to update a todo"""
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    if 'title' in data:
        todo.title = data['title']
    if 'description' in data:
        todo.description = data['description']
    if 'priority' in data:
        todo.priority = data['priority']
    if 'due_date' in data:
        if data['due_date']:
            try:
                todo.due_date = datetime.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'error': 'Invalid due date format'}), 400
        else:
            todo.due_date = None
    
    todo.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'todo': {
            'id': todo.id,
            'title': todo.title,
            'description': todo.description,
            'is_completed': todo.is_completed,
            'priority': todo.priority,
            'updated_at': todo.updated_at.isoformat()
        }
    })


@todo_bp.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@login_required
def api_toggle_todo(todo_id):
    """API endpoint to toggle todo completion status"""
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    
    if todo.is_completed:
        todo.mark_incomplete()
    else:
        todo.mark_complete()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_completed': todo.is_completed,
        'completed_at': todo.completed_at.isoformat() if todo.completed_at else None
    })


@todo_bp.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def api_delete_todo(todo_id):
    """API endpoint to delete a todo"""
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(todo)
    db.session.commit()
    
    return jsonify({'success': True})


@todo_bp.route('/api/todos/dashboard')
@login_required
def api_dashboard_todos():
    """API endpoint to get todos for dashboard widget"""
    # Get incomplete todos ordered by priority and created date
    todos = Todo.query.filter_by(
        user_id=current_user.id,
        is_completed=False
    ).order_by(
        db.case(
            (Todo.priority == 'high', 1),
            (Todo.priority == 'medium', 2),
            (Todo.priority == 'low', 3),
            else_=4
        ),
        Todo.created_at.desc()
    ).limit(5).all()
    
    pending_count = Todo.query.filter_by(
        user_id=current_user.id,
        is_completed=False
    ).count()
    
    return jsonify({
        'todos': [{
            'id': todo.id,
            'title': todo.title,
            'priority': todo.priority,
            'due_date': todo.due_date.isoformat() if todo.due_date else None,
            'created_at': todo.created_at.isoformat()
        } for todo in todos],
        'pending_count': pending_count
    })