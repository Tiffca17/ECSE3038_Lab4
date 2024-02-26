from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, BeforeValidator, Field, TypeAdapter
import motor.motor_asyncio
import uuid
from dotenv import dotenv_values
from bson import ObjectId
from pymongo import ReturnDocument
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

config = dotenv_values(".env")

client = motor.motor_asyncio.AsyncIOMotorClient(config["MONGO_URL"])
db = client.tank_man

app = FastAPI()

origins = [ "https://ecse3038-lab3-tester.netlify.app" ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PyObjectId = Annotated[str, BeforeValidator(str)]

class Tank(BaseModel):
    id: Optional[PyObjectId] = Field(alias = "_id", default = None)
    location: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None

class Profile(BaseModel):
    id: Optional[PyObjectId] = Field(alias = "_id", default = None)
    last_updated: Optional[str] = None
    username: str 
    role: str 
    color: str 

def check_color(v:str) -> str:
    assert re.search(r"^#([A-Fa-F0-9]{6}|[A-Fa-F0-9]{3})$",v)
    return v

async def edit_profile():
    only_profile = await db["profiles"].find().to_list(1)
    time = datetime.now().strftime("%m/%d/%Y, %I:%M:%S %p")
    db["profiles"].update_one({"_id": only_profile[0]["_id"]},{"$set": {"last_updated":time}})  

@app.get("/profile")
async def get_profile():
    profiles =  await db["profiles"].find().to_list(1)
    if len(profiles) == 0:
        return {}
    profile = profiles[0]
    return Profile(**profile)

@app.post("/profile", status_code=201)
async def create_profile(profile: Profile):
    current_time = datetime.now().strftime("%m/%d/%Y, %I:%M:%S %p")
    profile_data = profile.model_dump()
    profile_data["last_updated"] = current_time
    all_profiles =  await db["profiles"].find().to_list(999)
    if len(all_profiles) == 1:
        return ("Cannot enter another profile")
    new_profile = await db["profiles"].insert_one(profile_data)
    created_profile = await db["profiles"].find_one({"_id": new_profile.inserted_id})
    return Profile(**created_profile)

@app.get("/tank")
async def get_tanks():
    tanks =  await db["tanks"].find().to_list(999)
    if len(tanks) == 0:
        return []
    return TypeAdapter(List[Tank]).validate_python(tanks)

@app.get("/tank/{id}")
async def get_tank(id:str):
    one_tank = await db["tanks"].find_one({"_id": ObjectId(id)})
    if one_tank is None:
        raise HTTPException(status_code=404, detail="Tank of id " + id + " not found.")
    return Tank(**one_tank)

@app.post("/tank", status_code=201)
async def create_tank(tank: Tank):
    new_tank = await db["tanks"].insert_one(tank.model_dump())
    await edit_profile()
    created_tank = await db["tanks"].find_one({"_id": new_tank.inserted_id})
    return Tank(**created_tank)

@app.patch("/tank/{id}", status_code=200)
async def update_tank(id:str, tank_update: Tank):
    updated_tank = await db["tanks"].update_one({"_id":ObjectId(id)},{"$set": tank_update.model_dump(exclude_unset = True)})
    await edit_profile()

    if updated_tank.modified_count > 0:
        patched_tank = await db["tanks"].find_one({"_id": ObjectId(id)})
        return Tank(**patched_tank)
    raise HTTPException(status_code=404, detail="Tank of id " + id + " not found.")

@app.delete("/tank/{id}", status_code=204)
async def delete_tank(id:str):
    deleted_tank = await db["tanks"].delete_one({"_id": ObjectId(id)})
    await edit_profile()
    if deleted_tank.deleted_count < 1:
        raise HTTPException(status_code=404, detail="Tank of id " + id + " not found.")