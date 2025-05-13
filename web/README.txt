this application is built differently 

i built a frontend for UI to interract with a wiper system
getting rain sensor data (i used dht11 to act as rain sensor)
sending commands to control wiper system :
front/back/both wipers
number of cycles 
speed 

this frontend communicate with mongodb via node.js backend web server getting
and posting data 

mongodb is like the middleman interfacing between backend and our master raspberry

the master rasp connect to mongodb to either get or post data to it 
master also send received control commands and send them via CAN or LIN bus to 
the slave raspberry (the other master node in CAN case)