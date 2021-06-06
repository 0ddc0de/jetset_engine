import logging

from ..util.lifter_helper import GymratLifter
from ..util.instr_helper import Instruction, ParseError
from ..util import JumpKind, Type
from .. import register
from ...const import U32
#from ...expr import *
#import claripy
l = logging.getLogger(__name__)
#from ...const import U32

class ARMInstruction(Instruction): # pylint: disable=abstract-method

    # NOTE: WARNING: There is no CPSR in VEX's ARM implementation
    # You must use straight nasty hacks instead.

    # NOTE 2: Something is goofy w/r/t archinfo and VEX; cc_op3 is used in ccalls, but there's
    # no cc_op3 in archinfo, angr itself uses cc_depn instead.  We do the same.

    def match_instruction(self, data, bitstrm):
        """
        ARM Instructions are pretty dense, so let's do what we can to weed them out
        """
        if 'c' in data and data['c'] == '1111':
            print('Parse Error: ', data)
            raise ParseError("Invalid ARM Instruction")

    def get_N(self):
        cc_op = self.get("cc_op", Type.int_32)
        cc_dep1 = self.get("cc_dep1", Type.int_32)
        cc_dep2 = self.get("cc_dep2", Type.int_32)
        cc_depn = self.get("cc_ndep", Type.int_32)
        return self.ccall(Type.int_32, "armg_calculate_flag_n", [cc_op, cc_dep1, cc_dep2, cc_depn])

    def get_C(self):
        cc_op = self.get("cc_op", Type.int_32)
        cc_dep1 = self.get("cc_dep1", Type.int_32)
        cc_dep2 = self.get("cc_dep2", Type.int_32)
        cc_depn = self.get("cc_ndep", Type.int_32)
        return self.ccall(Type.int_32, "armg_calculate_flag_c", [cc_op, cc_dep1, cc_dep2, cc_depn])

    def get_V(self):
        cc_op = self.get("cc_op", Type.int_32)
        cc_dep1 = self.get("cc_dep1", Type.int_32)
        cc_dep2 = self.get("cc_dep2", Type.int_32)
        cc_depn = self.get("cc_ndep", Type.int_32)
        return self.ccall(Type.int_32, "armg_calculate_flag_v", [cc_op, cc_dep1, cc_dep2, cc_depn])

    def get_Z(self):
        cc_op = self.get("cc_op", Type.int_32)
        cc_dep1 = self.get("cc_dep1", Type.int_32)
        cc_dep2 = self.get("cc_dep2", Type.int_32)
        cc_depn = self.get("cc_ndep", Type.int_32)
        return self.ccall(Type.int_32, "armg_calculate_flag_z", [cc_op.rdt, cc_dep1.rdt, cc_dep2.rdt, cc_depn.rdt])

    def evaluate_condition(self):
        # condition codes should be in 'c'
        cond = self.data['c']
        if cond == '0000':
            # equal, z set
            return self.get_Z() == 1
        elif cond == '0001':
            # not equal, Z clear
            return self.get_Z() == 0
        elif cond == '0010':
            # Carry, C set
            return self.get_C() == 1
        elif cond == '0011':
            # Carry Clear, C clear
            return self.get_C() == 0
        elif cond == '0100':
            # MI / neagative / N set
            return self.get_N() == 1
        elif cond == '0101':
            # PL / plus / positive / N clear
            return self.get_N() == 0
        elif cond == '0110':
            # VS / V set / Overflow
            return self.get_V() == 1
        elif cond == '0111':
            # VC / V Clear / no overflow
            return self.get_V() == 0
        elif cond == '1000':
            # Hi / unsigned higher / C set, Z clear
            return (self.get_C() == 1) & (self.get_Z() == 0)
        elif cond == '1001':
            # LS / C clear, Z set
            return (self.get_C() == 0) & (self.get_Z() == 1)
        elif cond == '1011':
            # LT / Less than / N != V
            return self.get_N() != self.get_V()
        elif cond == '1100':
            # GT / greater than / Z clear and (n == v)
            return (self.get_Z() == 1) & (self.get_N() != self.get_V())
        elif cond == '1101':
            # LE / less than or equal to / Z set OR (N != V)
            return (self.get_Z() == 1) | (self.get_N() != self.get_V())
        else:
            # No condition
            return None


class Instruction_MRC(ARMInstruction):
    name = "MRC"
    bin_format = 'cccc1110CCC1nnnnddddppppOOOOmmmm'
                 #11101110000100010001111100010000
    # c = cond
    # C = Coprocessor operation mode
    # d = CPd
    # O = Offset
    # p = CP#
    # n = CRn
    # m = CRm

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO at least look at the conditionals
        # TODO Clobber the dst reg of MCR
        # TODO maybe treat coproc regs as simple storage (even though they are very much not)
        #val = self.ccall(Type.int_32, "armg_mrc", [])
        dst = int(self.data['d'], 2)
        if dst == 15: #PC
            # if dst == PC, we only make the condition codes symbolic
            # PC and other CPSR registers are unaffected
            v0 = self.ccall(Type.int_32, "armg_mrc", []) 
            v1 = self.ccall(Type.int_32, "armg_mrc", [])
            v2 = self.ccall(Type.int_32, "armg_mrc", [])
            v3 = self.ccall(Type.int_32, "armg_mrc", [])
            self.put(v0, "cc_op" )
            self.put(v1, "cc_dep1" )
            self.put(v2, "cc_dep2" ) 
            self.put(v3, "cc_ndep" )
        else:
            coproc_num = int(self.data['p'],2)
            #operation = int(self.data['O'],2)
            operation = int(self.data['m'],2)
            # system coprocessor
            if coproc_num == 15 and operation == 0:
                val = self.ccall(Type.int_32, "armg_mrc_device_id", [])
            else:
                #print(coproc_num,operation)
                val = self.ccall(Type.int_32, "armg_mrc", [])
                self.put(val, dst)
        #l.debug("Ignoring MRC instruction at %#x.", self.addr)


class Instruction_MCR(ARMInstruction):
    name = "MCR"
    bin_format = 'cccc1110CCC0nnnnddddppppOOOOOOOO'
                 #11101110000000010000111100010000
    # c = cond
    # C = Coprocessor operation mode
    # d = CPd
    # O = Offset
    # p = CP#

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO at least look at the conditionals
        # TODO Clobber the dst reg of MCR
        # TODO maybe treat coproc regs as simple storage (even though they are very much not)
        #l.debug("Ignoring MCR instruction at %#x.", self.addr)
        self.ccall(Type.int_32, "armg_mcr", [])



class Instruction_MSR(ARMInstruction):
    name = "MSR"
    bin_format = 'cccc00i10d10xxxj1111ssssssssssss'
    #             11100011001000011111000010010001
    #             11100001011011111111000000000001

    def compute_result(self): # pylint: disable=arguments-differ
        #self.ccall(Type.int_32,"armg_msr", [None])
        l.debug("Ignoring MSR instruction at %#x. VEX cannot support this instruction. See pyvex/lifting/gym/arm_spotter.py", self.addr)


class Instruction_MRS(ARMInstruction):
    name = "MRS"
    bin_format = "cccc00010s001111dddd000000000000"

    def compute_result(self): # pylint: disable=arguments-differ
        #self.ccall(Type.int_32,"armg_mrs", [None])
        l.debug("Ignoring MRS instruction at %#x. VEX cannot support this instruction. See pyvex/lifting/gym/arm_spotter.py", self.addr)

class Instruction_CPS(ARMInstruction):
    name = "CPS"
    #bin_format = "11110001000011000000000010000000"
    bin_format = "111100010000iimm0ssssssfff0ddddd"
    # i = imod
    # m = mmod
    # s = SBZ
    # f = iflags
    # d = mode

    def compute_result(self): # pylint: disable=arguments-differ
        #self.ccall(Type.int_32,"armg_mrs", [None])
        l.debug("Ignoring CPS instruction at %#x. VEX cannot support this instruction. See pyvex/lifting/gym/arm_spotter.py", self.addr)



class Instruction_STM(ARMInstruction):
    name = "STM"
    bin_format = 'cccc100pu1w0bbbbrrrrrrrrrrrrrrrr'

    def match_instruction(self, data, bitstrm):
        # If we don't push anything, that's not real
        if int(data['r']) == 0:
            raise ParseError("Invalid STM instruction")
        return True

    def compute_result(self): # pylint: disable=arguments-differ
        l.warning("Ignoring STMxx ^ instruction at %#x. This mode is not implemented by VEX! See pyvex/lifting/gym/arm_spotter.py", self.addr)


class Instruction_LDM(ARMInstruction):
    name = "LDM"
    bin_format = 'cccc100PU1W1bbbbrrrrrrrrrrrrrrrr'

    def match_instruction(self, data, bitstrm):
        # If we don't push anything, that's not real
        if int(data['r']) == 0:
            #print("<<<<<<<<<, parser error on LDM >>>>>>>>>.")
            raise ParseError("Invalid LDM instruction")
        return True

    def compute_result(self): # pylint: disable=arguments-differ
        # test if PC will be set. If so, the jumpkind of this block should be Ijk_Ret
        l.warning("Spotting an LDM instruction at %#x.  This is not fully tested.  Prepare for errors.", self.addr)
        #l.warning(repr(self.rawbits))
        #l.warning(repr(self.data))
        #print("<<<<<<<<<<< computing result for LDM >>>>>>>>>")

        src_n = int(self.data['b'], 2)
        src = self.get(src_n, Type.int_32)

        for reg_num, bit in enumerate(self.data['r']):
            reg_num = 15 - reg_num
            if bit == '1':
                if self.data['P'] == '1':
                    if self.data['U'] == '0':
                        src += 4
                    else:
                        src -= 4
                val = self.load(src, Type.int_32)
                self.put(val, reg_num)
                if self.data['P'] == '0':
                    if self.data['U'] == '0':
                        src += 4
                    else:
                        src -= 4
                # If we touch PC, we're doing a RET!
                if reg_num == 15 and bit == '1':
                    cond = self.evaluate_condition()
                    if cond is not None:
                        self.jump(cond, val, JumpKind.Ret)
                    else:
                        self.jump(None, val, JumpKind.Ret)
        # Write-back
        if self.data['W'] == '1':
            self.put(src, src_n)


class Instruction_STC(ARMInstruction):
    name = 'STC'
    bin_format = 'cccc110PUNW0nnnnddddppppOOOOOOOO'

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO At least look at the conditionals
        l.debug("Ignoring STC instruction at %#x.", self.addr)


class Instruction_LDC(ARMInstruction):
    name = 'STC'
    bin_format = 'cccc110PUNW1nnnnddddppppOOOOOOOO'

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO At least look at the conditionals
        # TODO Clobber the dest reg of LDC
        # TODO Maybe clobber the dst reg of CDP, if we're really adventurous
        l.debug("Ignoring LDC instruction at %#x.", self.addr)

class Instruction_CDP(Instruction):
    name = "CDP"
    bin_format = 'cccc1110oooonnnnddddppppPPP0mmmm'
    # c = cond
    # d = CPd
    # O = Offset
    # p = CP#

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO At least look at the conditionals
        # TODO Maybe clobber the dst reg of CDP, if we're really adventurous
        l.debug("Ignoring CDP instruction at %#x.", self.addr)

class Instruction_SMC(Instruction):
    name = "SMC"
    bin_format = 'cccc000101100000000000000111dddd'

    # d = number of smc call

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO At least look at the conditionals
        l.debug("Ignoring SMC instruction at %#x.", self.addr)

##
## Thumb! (ugh)
##

class ThumbInstruction(Instruction): # pylint: disable=abstract-method

    def mark_instruction_start(self):
        self.irsb_c.imark(self.addr-1, self.bytewidth, 1)


class Instruction_tCPSID(ThumbInstruction):
    name = 'CPSID'
    bin_format = '101101x0011x0010'

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO haha lol yeah right
        l.debug("[thumb] Ignoring CPS instruction at %#x.", self.addr)

class Instruction_tMSR(ThumbInstruction):
    name = 'MSR'
    bin_format = '10x0mmmmxxxxxxxx11110011100Rrrrr'

    def compute_result(self): # pylint: disable=arguments-differ
        # TODO haha lol yeah right
        l.debug("[thumb] Ignoring MSR instruction at %#x.", self.addr)


class Instruction_WFI(ThumbInstruction):
    name = "WFI"
    bin_format = "10111111001a0000"
                 #1011111100110000

    def compute_result(self): # pylint: disable=arguments-differ
        l.debug("[thumb] Ignoring WFI instruction at %#x.", self.addr)


class ARMSpotter(GymratLifter):
    arm_instrs = [
        Instruction_MRC,
        Instruction_MCR,
        Instruction_MSR,
        Instruction_MRS,
        Instruction_STM,
        Instruction_LDM,
        Instruction_STC,
        Instruction_LDC,
        Instruction_CDP,
        Instruction_SMC,
        Instruction_CPS
    ]
    thumb_instrs = [Instruction_tCPSID,
                    Instruction_tMSR,
                    Instruction_WFI,
                    ]
    instrs = None

    def lift(self, disassemble=False, dump_irsb=False):
        if self.irsb.addr & 1:
            # Thumb!
            self.instrs = self.thumb_instrs
        else:
            self.instrs = self.arm_instrs
        super(ARMSpotter, self).lift(disassemble, dump_irsb)

register(ARMSpotter, "ARM")
register(ARMSpotter, "ARMEL")
