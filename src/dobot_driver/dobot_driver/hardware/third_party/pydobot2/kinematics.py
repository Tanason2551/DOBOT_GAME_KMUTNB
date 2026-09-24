"""
open-dobot inverse kinematics.
Implements inverse and forward kinematics functions.
Find firmware, driver and SDK at https://github.com/maxosprojects/open-dobot
Author: maxosprojects (March 18 2016)
Additional Authors: <put your name here>
Version 1.2.2
License: MIT
"""
import math

# Dimentions in mm
lengthRearArm = 135.0
lengthFrontArm = 160.0
# Horizontal distance from Joint3 to the center of the tool mounted on the end effector.
distanceTool = .0
# Joint1 height.
heightFromGround = .0

lengthRearSquared = pow(lengthRearArm, 2)
lengthFrontSquared = pow(lengthFrontArm, 2)

piHalf = math.pi / 2.0


def coordinatesFromAngles(baseAngle, rearArmAngle, frontArmAngle):
    radius = lengthRearArm * math.cos(rearArmAngle) + lengthFrontArm * math.cos(frontArmAngle) + distanceTool
    print(f"Radius: {radius}")
    x = radius * math.cos(baseAngle)
    y = radius * math.sin(baseAngle)
    z = heightFromGround - lengthFrontArm * math.sin(frontArmAngle) + lengthRearArm * math.sin(rearArmAngle)

    return x, y, z

def anglesFromCoordinates(x, y, z):
    '''
    http://www.learnaboutrobots.com/inverseKinematics.htm
    '''
    # Radius to the center of the tool.
    radiusTool = math.sqrt(pow(x, 2) + pow(y, 2))

    # Radius to joint3.
    radius = radiusTool - distanceTool

    baseAngle = math.atan2(y, x)

    # X coordinate of joint3.
    jointX = radius * math.cos(baseAngle)

    # Y coordinate of joint3.
    jointY = radius * math.sin(baseAngle)

    actualZ = z - heightFromGround

    # Imaginary segment connecting joint1 with joint2, squared.
    hypotenuseSquared = pow(actualZ, 2) + pow(radius, 2)
    hypotenuse = math.sqrt(hypotenuseSquared)

    q1 = math.atan2(actualZ, radius)
    q2 = math.acos(
        (lengthRearSquared - lengthFrontSquared + hypotenuseSquared) / (2.0 * lengthRearArm * hypotenuse))
    rearAngle = piHalf - (q1 + q2)
    frontAngle = piHalf - (math.acos((lengthRearSquared + lengthFrontSquared - hypotenuseSquared) / (
                2.0 * lengthRearArm * lengthFrontArm)) - rearAngle)

    return baseAngle, rearAngle, frontAngle

