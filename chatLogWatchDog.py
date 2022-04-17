from subprocess import Popen, PIPE
import optparse
#take in arguements
parser = optparse.OptionParser()
parser.add_option('--server', help='Pass the server name to chat log bot')
#parse arguements
(opts, args) = parser.parse_args()

if not opts.server:
	print('--server is required')
	exit(1)

Server = opts.server

while True:
	print("Chat Log Watch Dog has started watching chat log")
	p = Popen(['python', 'chatlog.py', '--server', f'{Server}'], stdout=PIPE, stderr=PIPE, shell=True)
	p.wait()
	stdout, stderr = p.communicate()
	result = stdout
	print(result)
	print(stderr)