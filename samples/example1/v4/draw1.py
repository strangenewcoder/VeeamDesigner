import os

from N2G import drawio_diagram

styles_dir = os.environ.get('STYLES')

diagram = drawio_diagram()
diagram.add_diagram("Page-1")
diagram.add_node(id="ESXI01",label="ESXI01",style=styles_dir+"/VMWAREESXI.txt",x_pos="560",y_pos="240",width="60",height="60",data={"ip": "192.168.42.11/24","role":"VMWAREESXI","other_roles":""})
diagram.add_node(id="ESXI02",label="ESXI02",style=styles_dir+"/VMWAREESXI.txt",x_pos="560",y_pos="400",width="60",height="60",data={"ip": "192.168.42.12/24","role":"VMWAREESXI","other_roles":""})
diagram.add_node(id="VBRBACKUPSERVER01",label="VBRBACKUPSERVER01",style=styles_dir+"/VBRBACKUPSERVER.txt",x_pos="160",y_pos="440",width="60",height="60",data={"ip": "192.168.42.1/24","role":"VBRBACKUPSERVER","other_roles":"VBRCONSOLE"})
diagram.add_node(id="VBRREPOWIN01",label="VBRREPOWIN01",style=styles_dir+"/VBRMOUNTSERVER.txt",x_pos="160",y_pos="40",width="60",height="60",data={"ip": "192.168.42.2/24","role":"VBRMOUNTSERVER","other_roles":"VBRBACKUPREPOSITORY,VBRBACKUPREPOSITORYWINDOWS,VBRPOWERNFS"})
diagram.add_node(id="VC01",label="VC01",style=styles_dir+"/VMWAREVCENTER.txt",x_pos="560",y_pos="80",width="60",height="60",data={"ip": "192.168.42.10/24","role":"VMWAREVCENTER","other_roles":""})
diagram.add_link("VBRBACKUPSERVER01","VBRREPOWIN01",src_label="443, 6162, 2500 to 3300",trgt_label="137, 139, 443, 445, 6160, 6161, 6162, 6170, 2500 to 3300")
diagram.add_link("VBRBACKUPSERVER01","ESXI01",trgt_label="443, 902")
diagram.add_link("VBRBACKUPSERVER01","ESXI02",trgt_label="443, 902")
diagram.add_link("VBRBACKUPSERVER01","VC01",trgt_label="443")
diagram.add_link("VBRREPOWIN01","ESXI01",src_label="111, 1058 to 2058, 1063 to 2063, 2049 to 3049",trgt_label="443")
diagram.add_link("VBRREPOWIN01","ESXI02",src_label="111, 1058 to 2058, 1063 to 2063, 2049 to 3049",trgt_label="443")
diagram.add_link("VBRREPOWIN01","VC01",trgt_label="443")
diagram.dump_file(filename="draw1.drawio", folder="./")
