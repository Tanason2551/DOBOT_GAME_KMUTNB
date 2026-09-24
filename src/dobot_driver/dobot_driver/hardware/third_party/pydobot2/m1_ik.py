import numpy as np
from math import sin, cos, sqrt, atan2

# taken from https://github.com/jmsalash/Robotics-Dobot-M1/


class m1_ik:
    def __init__(self):
        self.l1 = 0.2
        self.l2 = 0.2
        self.set_ee(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.set_dh()

    '''
    Set end effector offset and rotation
    '''

    def set_ee(self, xt, yt, zt, rxt, ryt, rzt):
        self.xt = xt
        self.yt = yt
        self.zt = zt
        self.rxt = rxt
        self.ryt = ryt
        self.rzt = rzt
        self.ee = [xt, yt, zt, rxt, ryt, rzt]
        self.set_dh()

    '''
    Set DH parameters for the Dobot M1
    '''

    def set_dh(self):
        self.a = [0, self.l1, self.l2, 0.0]
        self.alpha = [0, 0, 0, 0]
        self.d = [0, 0, 0, 0]
        self.theta = [0, 0, 0, 0]

    '''
    Create the Jacobian matrix for differential inverse kinematics
    Dimension is 6x4, but it could be reduced to 4x4 since there is no x/y rotations
    This would allow it to use the inverse matrix directly, but it would through an error when in singularity
    Instead pseudo-inverse will be used to get the lowest norm error
    '''

    def jacobian(self, q):
        j11 = 0.0
        j12 = -self.l1 * sin(q[1]) - self.l2 * sin(q[1] + q[2]) - self.xt * sin(q[1] + q[2] + q[3]) + self.yt * cos(
            q[1] + q[2] + q[3])
        j13 = -self.l2 * sin(q[1] + q[2]) - self.xt * sin(q[1] + q[2] + q[3]) + self.yt * cos(q[1] + q[2] + q[3])
        j14 = -self.xt * sin(q[1] + q[2] + q[3]) + self.yt * cos(q[1] + q[2] + q[3])

        j21 = 0.0
        j22 = self.l1 * cos(q[1]) + self.l2 * cos(q[1] + q[2]) + self.xt * cos(q[1] + q[2] + q[3]) - self.yt * sin(
            q[1] + q[2] + q[3])
        j23 = self.l2 * cos(q[1] + q[2]) + self.xt * cos(q[1] + q[2] + q[3]) - self.yt * sin(q[1] + q[2] + q[3])
        j24 = self.xt * cos(q[1] + q[2] + q[3]) - self.yt * sin(q[1] + q[2] + q[3])

        J = np.asarray(
            [[j11, j12, j13, j14],
             [j21, j22, j23, j24],
             [1, 0, 0, 0],
             [0, 0, 0, 0],
             [0, 0, 0, 0],
             [0, 1, 1, 1]])

        return J

    '''
    Get joint velocities based on current configuration and initial/final positions
    '''

    def diff_ik(self, q_cur, p_cur, p_des):
        #        print('Move from {} to {}'.format(p_cur, p_des))
        pdot_des = p_des - p_cur

        J = self.jacobian(q_cur)
        J_pinv = np.linalg.pinv(J)
        qdot_ik = np.matmul(J_pinv, pdot_des)

        return qdot_ik

    '''
    The Dobot M1 can be seen as a planar RRR manipulator, with Z translation
    Closed form analyticial inverse kinematics solution
    '''

    def closed_ik(self, px, py, pz, rx, ry, rz):
        phi = rz
        px = px - self.xt * cos(phi) - self.yt * sin(phi)
        py = py - self.xt * sin(phi) - self.yt * cos(phi)
        c3 = (px ** 2 + py ** 2 - self.l1 ** 2 - self.l2 ** 2) / (2 * self.l1 * self.l2)
        s3 = sqrt(1 - (c3 ** 2))
        # 2 solutions +s3 and -s3
        q3p = atan2(s3, c3)
        q3n = atan2(-s3, c3)
        q2p = atan2(py, px) - atan2(self.l2 * s3, self.l1 + self.l2 * c3)
        q2n = atan2(py, px) - atan2(-self.l2 * s3, self.l1 + self.l2 * c3)
        q1 = pz - self.zt
        q4p = rz - q2p - q3p
        q4n = rz - q2n - q3n

        return (np.asarray([q1, q2p, q3p, q4p]), np.asarray([q1, q2n, q3n, q4n]))
