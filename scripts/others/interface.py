#!/usr/bin/env python3
from sshkeyboard import listen_keyboard, stop_listening
from tvmc import MotionController, DoF, ControlMode
import blessings
import rospy
from time import sleep
from threading import Thread
from std_msgs.msg import Float32MultiArray, Int32MultiArray, Float32
from geometry_msgs.msg import Vector3
#import PID_CONSTANTS


#DATA_SOURCE = "sensors"
DATA_SOURCE = "sensors"

HEAVE_TARGET_OFFSET = -0.08
HEAVE_KP = -25 # -90 #-70 #-60 #-40 #-50 # -100
HEAVE_KI = 0
HEAVE_KD = 60 #30# 5.2 #6.5
HEAVE_TARGET = 0.35 - HEAVE_TARGET_OFFSET
HEAVE_ACCEPTABLE_ERROR = 0.05
HEAVE_OFFSET = 0 #-0.13 # 0

PITCH_TARGET_OFFSET = -5
PITCH_KP = -0.25#-0.25  #0.8
PITCH_KI = 0#0.02
PITCH_KD = 50# 0.15 #0.2
PITCH_TARGET = 0 - PITCH_TARGET_OFFSET
PITCH_ACCEPTABLE_ERROR = 1
PITCH_OFFSET = 0 #5

ROLL_KP = 0#-0.2 #0.1
ROLL_KI = 0
ROLL_KD = 0
ROLL_TARGET = 3
ROLL_ACCEPTABLE_ERROR = 1

YAW_TARGET_OFFSET = -7.3
YAW_KP = -2
YAW_KI = 0.02
YAW_KD = 12
YAW_TARGET  = 161 - YAW_TARGET_OFFSET
YAW_ACCEPTABLE_ERROR = 0.05

m = MotionController()
term = blessings.Terminal()

closed_loop_enabled = set()
currently_doing = set()
diagnostics = {}
keep_rendering = True


def render():
    while keep_rendering:
        with term.hidden_cursor():
            print(term.fullscreen())
            print(term.clear())
            print(term.red(term.bold("TVMC Controller")))
            print("Press esc. at any point to exit.\n")
            x = 1000

            while keep_rendering and x:
                with term.location(0, 4):
                    print(term.bold("Diagnostics"))

                    for diagnostic in diagnostics:
                        print(
                            f"{diagnostic}:", diagnostics[diagnostic], term.clear_eol()
                        )

                    print(term.clear_eol())
                    print(term.bold("Control"), term.clear_eol())

                    if len(closed_loop_enabled):
                        print(
                            "PID: ",
                            [x.name for x in closed_loop_enabled],
                            term.clear_eol(),
                        )

                    print(
                        "Manual Thrust: ",
                        [x.name for x in currently_doing],
                        term.clear_eol(),
                    )

                    print(term.clear_eol())
                x = x - 1
                sleep(0.01)
    print(term.exit_fullscreen())


def thrust(dof, rev=1):
    def p():
        if dof in closed_loop_enabled:
            return

        m.set_thrust(dof, 50 * rev)
        currently_doing.add(dof)

    def r():
        if dof in closed_loop_enabled:
            return

        m.set_thrust(dof, 0)
        currently_doing.remove(dof)

    return p, r


def pid_enable(dof):
    m.set_control_mode(dof, ControlMode.CLOSED_LOOP)
    closed_loop_enabled.add(dof)

    if dof == DoF.HEAVE:
        m.set_pid_constants(
            DoF.HEAVE,
            HEAVE_KP,
            HEAVE_KI,
            HEAVE_KD,
            HEAVE_ACCEPTABLE_ERROR,
            HEAVE_OFFSET,
        )
        m.set_pid_limits(DoF.HEAVE, -10, 10, -25, 25)
        m.set_target_point(DoF.HEAVE, HEAVE_TARGET)

    if dof == DoF.PITCH:
        m.set_pid_constants(
            DoF.PITCH, PITCH_KP, PITCH_KI, PITCH_KD, PITCH_ACCEPTABLE_ERROR
        )
        m.set_pid_limits(DoF.PITCH, -10, 10, -25, 25)
        m.set_target_point(DoF.PITCH, PITCH_TARGET)

    if dof == DoF.ROLL:
        m.set_pid_constants(DoF.ROLL, ROLL_KP, ROLL_KI, ROLL_KD, ROLL_ACCEPTABLE_ERROR)
        m.set_target_point(DoF.ROLL, ROLL_TARGET)

    if dof == DoF.YAW:
        m.set_pid_constants(DoF.YAW, YAW_KP, YAW_KI, YAW_KD, YAW_ACCEPTABLE_ERROR)
        m.set_pid_limits(DoF.YAW, -10, 10, -25, 25)
        m.set_target_point(DoF.YAW, YAW_TARGET)


def pid_disable(dof):
    m.set_control_mode(dof, ControlMode.OPEN_LOOP)
    closed_loop_enabled.remove(dof)


def pid(dof):
    def toggle():
        if dof in closed_loop_enabled:
            pid_disable(dof)
        else:
            pid_enable(dof)

    return [toggle, lambda: None]


mp = {
    "w": thrust(DoF.SURGE, 3),
    "a": thrust(DoF.YAW, -1),
    "s": thrust(DoF.SURGE, -1),
    "d": thrust(DoF.YAW, 1),
    "z": thrust(DoF.HEAVE, 1),
    "x": thrust(DoF.HEAVE, -1),
    "q": thrust(DoF.ROLL, 1),
    "e": thrust(DoF.ROLL, -1),
    "u": thrust(DoF.PITCH, 1),
    "i": thrust(DoF.PITCH, -1),
    "h": pid(DoF.HEAVE),
    "j": pid(DoF.PITCH),
    "k": pid(DoF.ROLL),
    "l": pid(DoF.YAW),
}


def press(key):
    if key in mp:
        mp[key][0]()


def release(key):
    if key in mp:
        mp[key][1]()


def data():
    def set(name, data):
        diagnostics[name] = data

    # subscribe to any topics that you'd like to subscribe to,
    # and then make them update diagnostics_data to have stuff update
    # in real time

    # you should also set up subcribers to
    # update the current point for all PID controllers here

    rospy.Subscriber(
        "/rose_tvmc/thrust", Float32MultiArray, lambda x: set("Thrust", x.data)
    )

    rospy.Subscriber("/control/pwm", Int32MultiArray, lambda x: set("PWM", x.data))

    rospy.Subscriber(
        f"/{DATA_SOURCE}/linear_acceleration",
        Vector3,
        lambda x: set("Linear Acceleration", (x.x, x.y, x.z)),
    )

    rospy.Subscriber(
        f"/{DATA_SOURCE}/angular_velocity",
        Vector3,
        lambda x: set("Angular Velocity", (x.x, x.y, x.z)),
    )

    rospy.Subscriber(
        f"/{DATA_SOURCE}/magnetic_field",
        Vector3,
        lambda x: set("Magnetic Field", (x.x, x.y, x.z)),
    )

    def orientation(x):
        m.set_current_point(DoF.ROLL, x.x)
        m.set_current_point(DoF.PITCH, x.y)
        m.set_current_point(DoF.YAW, x.z)
        set("Roll", x.x)
        set("Pitch", x.y)
        set("Yaw", x.z)
        

    rospy.Subscriber(f"/{DATA_SOURCE}/orientation", Vector3, orientation)

    def depth(d):
        m.set_current_point(DoF.HEAVE, d.data)
        set("Depth", d.data)

    rospy.Subscriber(f"/{DATA_SOURCE}/depth", Float32, depth)


if __name__ == "__main__":
    print(term.red("Starting nodes.\n\n"))
    m.start()

    renderer = Thread(target=render, daemon=True)
    renderer.start()

    data()

    listen_keyboard(
        on_press=press,
        on_release=release,
    )

    keep_rendering = False
    print(term.clear())
    print("Bye-bye!\n\n")
    exit(0)
