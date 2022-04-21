from subprocess import Popen

while True:
	print("Starting Shop Bot")
	p = Popen("py main.py", shell=True)
	p.wait()
