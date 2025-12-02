A terrain data/heightmap viewer for James Cameron's Avatar: The Game. Entirely made with AI code. I'm not a coder.

Allows the user to view and export the terrain as a heightmap for use in other 3D software such as blender or Unreal Engine.

This script basically reads the sectors/chunks of the terrain and pieces them together to make a fully viewable heightmap.

-Todo List:

1. Fix shadows.xbt reader
2. Scaling

-Note:
This script is SUPER WIP. The initial/public branch has an older simple version, the dev branch will have a more up to date version but with more bugs and things that need fixing.

-Use:

Simply double click the python file and select the "sdat" folder of the map you want to view, such as `levels\sp_hellsgate_01_l\generated\sdat`
It should automatically open the heightmap and tell what where all the sectors are. The script currently has a basic click and drag distance measurer but... i can't really speak for it's accuracy however 1 coordinate = 1 meter

<img width="1202" height="984" alt="image" src="https://github.com/user-attachments/assets/9c118468-140e-4d04-a623-4e427309b9be" />
<img width="1202" height="984" alt="image" src="https://github.com/user-attachments/assets/8228a251-d71a-4c41-8d97-515760ce1657" />
<img width="1202" height="984" alt="image" src="https://github.com/user-attachments/assets/1c558ced-b59e-4d15-acb5-272dd1183a95" />
