from app import create_app

app = create_app()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5010))
    app.run(host='0.0.0.0', debug=True, port=port)