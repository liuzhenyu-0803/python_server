# 导入FastAPI框架相关组件  
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status  
# 导入CORS中间件，用于处理跨域资源共享  
from fastapi.middleware.cors import CORSMiddleware  
# 导入Pydantic模型用于数据验证和序列化  
from pydantic import BaseModel, Field  
# 导入类型提示模块  
from typing import List, Dict, Optional  
# 导入生成唯一ID的模块  
import uuid  
# 导入异步IO模块  
import asyncio  
# 导入ASGI服务器  
import uvicorn  
# 导入日志模块  
import logging  
# 导入日期时间模块  
from datetime import datetime  

# 配置日志  
logging.basicConfig(level=logging.INFO)  # 设置日志级别为INFO  
logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器  

# 创建FastAPI应用实例  
app = FastAPI(title="双模式通信服务器", description="同时支持HTTP和WebSocket的FastAPI示例")  

# 添加CORS中间件支持跨域请求  
app.add_middleware(  
    CORSMiddleware,  
    allow_origins=["*"],  # 允许所有来源的请求，生产环境应当限制具体域名  
    allow_credentials=True,  # 允许发送凭证信息  
    allow_methods=["*"],  # 允许所有HTTP方法  
    allow_headers=["*"],  # 允许所有HTTP头  
)  

# 定义消息数据模型  
class Message(BaseModel):  
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 消息唯一ID，默认自动生成UUID  
    content: str  # 消息内容  
    sender: str   # 发送者  
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())  # 时间戳，默认为当前时间的ISO格式  

# 定义用户创建请求数据模型  
class UserCreate(BaseModel):  
    username: str  # 用户名  
    email: str     # 邮箱  

# 定义用户响应数据模型，继承自UserCreate并添加ID字段  
class User(UserCreate):  
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # 用户唯一ID，默认自动生成UUID  

# 内存数据存储  
users: Dict[str, User] = {}  # 存储用户信息的字典，键为用户ID  
messages: List[Message] = []  # 存储消息的列表  

# WebSocket连接管理器类，用于管理活跃的WebSocket连接  
class ConnectionManager:  
    def __init__(self):  
        self.active_connections: List[WebSocket] = []  # 存储活跃WebSocket连接的列表  
    
    # 处理新的WebSocket连接  
    async def connect(self, websocket: WebSocket):  
        await websocket.accept()  # 接受WebSocket连接  
        self.active_connections.append(websocket)  # 将连接添加到活跃连接列表  
        logger.info(f"新的WebSocket连接。当前连接数: {len(self.active_connections)}")  
    
    # 处理WebSocket断开连接  
    def disconnect(self, websocket: WebSocket):  
        self.active_connections.remove(websocket)  # 从活跃连接列表中移除断开的连接  
        logger.info(f"WebSocket连接断开。当前连接数: {len(self.active_connections)}")  
    
    # 向所有活跃的WebSocket连接广播消息  
    async def broadcast(self, message: Message):  
        for connection in self.active_connections:  
            await connection.send_json(message.dict())  # 发送JSON格式的消息  

# 创建连接管理器实例  
manager = ConnectionManager()  

# HTTP根路径端点，返回服务器状态信息  
@app.get("/")  
async def root():  
    return {"message": "服务器运行中，支持HTTP和WebSocket通信"}  

# HTTP端点：获取所有用户  
@app.get("/users", response_model=List[User])  
async def get_users():  
    return list(users.values())  # 返回所有用户信息的列表  

# HTTP端点：创建新用户  
@app.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)  
async def create_user(user: UserCreate):  
    # 检查用户名是否已存在  
    if any(u.username == user.username for u in users.values()):  
        raise HTTPException(status_code=400, detail="用户名已存在")  
    
    # 创建新用户对象  
    new_user = User(**user.dict())  
    users[new_user.id] = new_user  # 将新用户添加到用户字典中  
    logger.info(f"创建新用户: {new_user.username}")  
    return new_user  # 返回新创建的用户信息  

# HTTP端点：获取消息历史  
@app.get("/messages", response_model=List[Message])  
async def get_messages(limit: Optional[int] = 10):  
    return messages[-limit:]  # 返回最近的limit条消息  

# HTTP端点：发送新消息  
@app.post("/messages", response_model=Message)  
async def post_message(message_data: dict):  
    # 创建新消息对象  
    message = Message(  
        content=message_data["content"],  
        sender=message_data["sender"]  
    )  
    messages.append(message)  # 将新消息添加到消息列表  
    
    # 通过WebSocket广播新消息到所有连接的客户端  
    await manager.broadcast(message)  
    
    return message  # 返回新创建的消息  

# WebSocket端点：处理聊天消息  
@app.websocket("/ws")  
async def websocket_endpoint(websocket: WebSocket):  
    await manager.connect(websocket)  # 连接WebSocket  
    try:  
        # 发送最近的消息历史给新连接的客户端  
        for message in messages[-10:]:  
            await websocket.send_json(message.dict())  
        
        # 持续处理接收到的消息  
        while True:  
            data = await websocket.receive_json()  # 接收客户端发送的JSON消息  
            message = Message(content=data["content"], sender=data["sender"])  # 创建消息对象  
            messages.append(message)  # 添加到消息列表  
            await manager.broadcast(message)  # 广播给所有连接的客户端  
            
    except WebSocketDisconnect:  
        # 处理WebSocket断开连接的情况  
        manager.disconnect(websocket)  
    except Exception as e:  
        # 处理其他异常  
        logger.error(f"WebSocket错误: {str(e)}")  
        manager.disconnect(websocket)  

# WebSocket端点：心跳检测  
@app.websocket("/ws/heartbeat")  
async def heartbeat(websocket: WebSocket):  
    await websocket.accept()  # 接受WebSocket连接  
    try:  
        while True:  
            # 每5秒发送一次心跳消息  
            await websocket.send_text("heartbeat")  
            await asyncio.sleep(5)  # 异步等待5秒  
    except WebSocketDisconnect:  
        logger.info("心跳连接断开")  

# 主程序入口，启动服务器  
if __name__ == "__main__":  
    # 使用uvicorn启动FastAPI应用  
    # host="0.0.0.0"表示监听所有网络接口  
    # port=8000表示监听8000端口  
    # reload=True表示代码变更时自动重新加载  
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)