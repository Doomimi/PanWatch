import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
try:
    s = socket.create_connection((host, port), timeout=4)
    print("PROXY_OK " + host)
    s.close()
except Exception as e:
    print("PROXY_FAIL " + host + " " + type(e).__name__)