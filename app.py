import os
import re
import flask
import subprocess
import flask_socketio
import models
from flask import request, session, escape
from githubOauth import auth_user, get_user_data, get_user_repos, get_user_repo_tree, get_user_file_contents
from settings import db, app

socketio = flask_socketio.SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

states = set()
@app.route('/')
def main():
    return flask.render_template('index.html')

@socketio.on('connect')
def on_connect():
    print(f"{request.sid} connected")
    socketio.emit('test', {
        'message': 'Server is up!'
    })
    
@socketio.on('disconnect')
def on_disconnect():
    print(f"{request.sid} disconnected")
    user = models.Users.query.filter_by(sid=request.sid).first()
    if user is not None:
        db.session.delete(user)
        db.session.commit()

@socketio.on('store state')
def on_store_state(data):
    states.add(data['state'])
    
@socketio.on('auth user')
def on_auth_user(data):
    code = data['code']
    state = data['state']
    if state not in states:
        print('state: ', state, ' does not match any waiting states')
    else:
        auth_user(code, state)
        socketio.emit('user data', get_user_data(request.sid))
        
@socketio.on('get repos')
def on_get_repos():
    socketio.emit('repos', get_user_repos(request.sid), request.sid)
    
@socketio.on('get repo tree')
def on_get_repo_tree(data):
    socketio.emit('repo tree', get_user_repo_tree(request.sid, data['repo_url']))
    
@socketio.on('get file contents')
def on_get_file_contents(data):
    socketio.emit('file contents', get_user_file_contents(request.sid, data['content_url']))

@socketio.on('lint')
def code(data):
    linter = data['linter']
    code = data['code']
    filename = data['uuid'] + ('.py' if linter == 'pylint' else '.js')

    # get the current script path.
    here = os.path.dirname(os.path.realpath(__file__))
    subdir = "userfiles"

    filepath = os.path.join(here, subdir, filename)
    file = open(filepath, "w")
    file.write(code)
    file.close()

    if linter == 'eslint':
        result = subprocess.run([linter, '-f', 'html', f'./userfiles/{filename}'],
                                stdout=subprocess.PIPE).stdout.decode("utf-8")

        result = result.replace('style="display:none"', 'style="display:table-row"')
        result = re.sub(r'\[\+\].*.js', 'eslint', result)
        socketio.emit('output', {
            'linter': linter,
            'output': result
        }, room=request.sid)

        subprocess.run(['rm', '-r', f'./userfiles/{filename}'])

if __name__ == '__main__':
    import models
    models.db.create_all()
    socketio.run(
        app,
        host=os.getenv('IP', '0.0.0.0'),
        port=int(os.getenv('PORT', 3000))
    )
