# // 连接WebSocket  
# const socket = new WebSocket('ws://localhost:8000/ws');  

# // 处理收到的消息  
# socket.onmessage = function(event) {  
#   const message = JSON.parse(event.data);  
#   console.log('收到消息:', message);  
#   // 在界面上显示消息  
# };  

# // 发送消息  
# function sendMessage(content, sender) {  
#   socket.send(JSON.stringify({  
#     content: content,  
#     sender: sender  
#   }));  
# }  