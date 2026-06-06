import os
import requests
def send_simple_message():
  	return requests.post(
  		"https://api.mailgun.net/v3/sandboxff22017af3e948859b992f12e42110ae.mailgun.org/messages",
  		auth=("api", os.getenv('API_KEY', 'API_KEY')),
  		data={"from": "Mailgun Sandbox <postmaster@sandboxff22017af3e948859b992f12e42110ae.mailgun.org>",
			"to": "Kyle Gagen <kyle.gagen@kmg123enterprises.com>",
  			"subject": "Hello Kyle Gagen",
  			"text": "Congratulations Kyle Gagen, you just sent an email with Mailgun! You are truly awesome!"})