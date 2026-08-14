import os

from N2G import drawio_diagram

styles_dir = os.environ.get('STYLES')

diagram = drawio_diagram()
diagram.add_diagram("Page-1")
diagram.add_node(id="VBRBACKUPSERVER01",label="VBRBACKUPSERVER01",style=styles_dir+"/VBRBACKUPSERVER.txt",x_pos="150",y_pos="360",width="60",height="60",data={"ip": "192.168.42.1/24","role":"VBRBACKUPSERVER","other_roles":"VBRCONSOLE"})
diagram.add_node(id="VBRREPOWIN01",label="VBRREPOWIN01",style=styles_dir+"/VBRMOUNTSERVER.txt",x_pos="150",y_pos="80",width="60",height="60",data={"ip": "192.168.42.2/24","role":"VBRMOUNTSERVER","other_roles":"VBRBACKUPREPOSITORY,VBRBACKUPREPOSITORYWINDOWS,VBRPOWERNFS"})
diagram.add_link("VBRBACKUPSERVER01","VBRREPOWIN01",src_label="443, 6162, 2500 to 3300",trgt_label="137, 139, 443, 445, 6160, 6161, 6162, 6170, 2500 to 3300")
diagram.dump_file(filename="draw1.drawio", folder="./")
