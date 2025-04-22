
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
from typing import List

app = FastAPI()

# HTTP接口：数据模型定义
class Message(BaseModel):
    content: str

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# HTTP GET端点
@app.get("/hello")
async def hello():
    return {"message": "Hello from FastAPI!"}

# HTTP POST端点
@app.post("/send")
async def send_message(message: Message):
    return {"received": message.content}

# WebSocket端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"客户端说: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 主函数
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# http测试
# http://127.0.0.1:8000/hello  

# websocket测试
# ws://127.0.0.1:8000/ws
