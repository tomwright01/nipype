# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
from builtins import open, open

import os
import tempfile
import shutil

import pytest
from nipype.utils.filemanip import split_filename, filename_to_list
from .. import preprocess as fsl
from nipype.interfaces.fsl import Info
from nipype.interfaces.base import File, TraitError, Undefined, isdefined
from nipype.interfaces.fsl import no_fsl


def fsl_name(obj, fname):
    """Create valid fsl name, including file extension for output type.
    """
    ext = Info.output_type_to_ext(obj.inputs.output_type)
    return fname + ext


@pytest.fixture()
def setup_infile(tmpdir):
    ext = Info.output_type_to_ext(Info.output_type())
    tmp_dir = str(tmpdir)
    tmp_infile = os.path.join(tmp_dir, 'foo' + ext)
    open(tmp_infile, 'w')

    return (tmp_infile, tmp_dir)


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_bet(setup_infile):
    tmp_infile, tp_dir = setup_infile
    better = fsl.BET()
    assert better.cmd == 'bet'

    # Test raising error with mandatory args absent
    with pytest.raises(ValueError):
        better.run()

    # Test generated outfile name
    better.inputs.in_file = tmp_infile
    outfile = fsl_name(better, 'foo_brain')
    outpath = os.path.join(os.getcwd(), outfile)
    realcmd = 'bet %s %s' % (tmp_infile, outpath)
    assert better.cmdline == realcmd
    # Test specified outfile name
    outfile = fsl_name(better, '/newdata/bar')
    better.inputs.out_file = outfile
    realcmd = 'bet %s %s' % (tmp_infile, outfile)
    assert better.cmdline == realcmd

    # infile foo.nii doesn't exist
    def func():
        better.run(in_file='foo2.nii', out_file='bar.nii')
    with pytest.raises(TraitError):
        func()

    # Our options and some test values for them
    # Should parallel the opt_map structure in the class for clarity
    opt_map = {
        'outline': ('-o', True),
        'mask': ('-m', True),
        'skull': ('-s', True),
        'no_output': ('-n', True),
        'frac': ('-f 0.40', 0.4),
        'vertical_gradient': ('-g 0.75', 0.75),
        'radius': ('-r 20', 20),
        'center': ('-c 54 75 80', [54, 75, 80]),
        'threshold': ('-t', True),
        'mesh': ('-e', True),
        'surfaces': ('-A', True)
        # 'verbose': ('-v', True),
        # 'flags': ('--i-made-this-up', '--i-made-this-up'),
    }
    # Currently we don't test -R, -S, -B, -Z, -F, -A or -A2

    # test each of our arguments
    better = fsl.BET()
    outfile = fsl_name(better, 'foo_brain')
    outpath = os.path.join(os.getcwd(), outfile)
    for name, settings in list(opt_map.items()):
        better = fsl.BET(**{name: settings[1]})
        # Add mandatory input
        better.inputs.in_file = tmp_infile
        realcmd = ' '.join([better.cmd, tmp_infile, outpath, settings[0]])
        assert better.cmdline == realcmd

# test fast


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_fast(setup_infile):
    tmp_infile, tp_dir = setup_infile
    faster = fsl.FAST()
    faster.inputs.verbose = True
    fasted = fsl.FAST(in_files=tmp_infile, verbose=True)
    fasted2 = fsl.FAST(in_files=[tmp_infile, tmp_infile], verbose=True)

    assert faster.cmd == 'fast'
    assert faster.inputs.verbose == True
    assert faster.inputs.manual_seg == Undefined
    assert faster.inputs != fasted.inputs
    assert fasted.cmdline == 'fast -v -S 1 %s' % (tmp_infile)
    assert fasted2.cmdline == 'fast -v -S 2 %s %s' % (tmp_infile, tmp_infile)

    faster = fsl.FAST()
    faster.inputs.in_files = tmp_infile
    assert faster.cmdline == 'fast -S 1 %s' % (tmp_infile)
    faster.inputs.in_files = [tmp_infile, tmp_infile]
    assert faster.cmdline == 'fast -S 2 %s %s' % (tmp_infile, tmp_infile)

    # Our options and some test values for them
    # Should parallel the opt_map structure in the class for clarity
    opt_map = {'number_classes': ('-n 4', 4),
               'bias_iters': ('-I 5', 5),
               'bias_lowpass': ('-l 15', 15),
               'img_type': ('-t 2', 2),
               'init_seg_smooth': ('-f 0.035', 0.035),
               'segments': ('-g', True),
               'init_transform': ('-a %s' % (tmp_infile), '%s' % (tmp_infile)),
               'other_priors': ('-A %s %s %s' % (tmp_infile, tmp_infile,
                                                 tmp_infile),
                                (['%s' % (tmp_infile),
                                  '%s' % (tmp_infile),
                                  '%s' % (tmp_infile)])),
               'no_pve': ('--nopve', True),
               'output_biasfield': ('-b', True),
               'output_biascorrected': ('-B', True),
               'no_bias': ('-N', True),
               'out_basename': ('-o fasted', 'fasted'),
               'use_priors': ('-P', True),
               'segment_iters': ('-W 14', 14),
               'mixel_smooth': ('-R 0.25', 0.25),
               'iters_afterbias': ('-O 3', 3),
               'hyper': ('-H 0.15', 0.15),
               'verbose': ('-v', True),
               'manual_seg': ('-s %s' % (tmp_infile), '%s' % (tmp_infile)),
               'probability_maps': ('-p', True),
               }

    # test each of our arguments
    for name, settings in list(opt_map.items()):
        faster = fsl.FAST(in_files=tmp_infile, **{name: settings[1]})
        assert faster.cmdline == ' '.join([faster.cmd, settings[0],
                                           "-S 1 %s" % tmp_infile])


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_fast_list_outputs(setup_infile):
    ''' By default (no -o), FSL's fast command outputs files into the same
    directory as the input files. If the flag -o is set, it outputs files into
    the cwd '''
    def _run_and_test(opts, output_base):
        outputs = fsl.FAST(**opts)._list_outputs()
        for output in outputs.values():
            if output:
                for filename in filename_to_list(output):
                    assert os.path.realpath(filename).startswith(os.path.realpath(output_base))

    # set up
    tmp_infile, indir = setup_infile
    cwd = tempfile.mkdtemp()
    os.chdir(cwd)
    assert indir != cwd
    out_basename = 'a_basename'

    # run and test
    opts = {'in_files': tmp_infile}
    input_path, input_filename, input_ext = split_filename(tmp_infile)
    _run_and_test(opts, os.path.join(input_path, input_filename))

    opts['out_basename'] = out_basename
    _run_and_test(opts, os.path.join(cwd, out_basename))


@pytest.fixture()
def setup_flirt(tmpdir):
    ext = Info.output_type_to_ext(Info.output_type())
    tmp_dir = str(tmpdir)
    _, infile = tempfile.mkstemp(suffix=ext, dir=tmp_dir)
    _, reffile = tempfile.mkstemp(suffix=ext, dir=tmp_dir)

    return (tmp_dir, infile, reffile)


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_flirt(setup_flirt):
    # setup
    tmpdir, infile, reffile = setup_flirt

    flirter = fsl.FLIRT()
    assert flirter.cmd == 'flirt'

    flirter.inputs.bins = 256
    flirter.inputs.cost = 'mutualinfo'

    flirted = fsl.FLIRT(in_file=infile, reference=reffile,
                        out_file='outfile', out_matrix_file='outmat.mat',
                        bins=256,
                        cost='mutualinfo')
    flirt_est = fsl.FLIRT(in_file=infile, reference=reffile,
                          out_matrix_file='outmat.mat',
                          bins=256,
                          cost='mutualinfo')
    assert flirter.inputs != flirted.inputs
    assert flirted.inputs != flirt_est.inputs

    assert flirter.inputs.bins == flirted.inputs.bins
    assert flirter.inputs.cost == flirt_est.inputs.cost
    realcmd = 'flirt -in %s -ref %s -out outfile -omat outmat.mat ' \
        '-bins 256 -cost mutualinfo' % (infile, reffile)
    assert flirted.cmdline == realcmd

    flirter = fsl.FLIRT()
    # infile not specified
    with pytest.raises(ValueError):
        flirter.run()
    flirter.inputs.in_file = infile
    # reference not specified
    with pytest.raises(ValueError):
        flirter.run()
    flirter.inputs.reference = reffile
    # Generate outfile and outmatrix
    pth, fname, ext = split_filename(infile)
    outfile = fsl_name(flirter, '%s_flirt' % fname)
    outmat = '%s_flirt.mat' % fname
    realcmd = 'flirt -in %s -ref %s -out %s -omat %s' % (infile, reffile,
                                                         outfile, outmat)
    assert flirter.cmdline == realcmd

    _, tmpfile = tempfile.mkstemp(suffix='.nii', dir=tmpdir)
    # Loop over all inputs, set a reasonable value and make sure the
    # cmdline is updated correctly.
    for key, trait_spec in sorted(fsl.FLIRT.input_spec().traits().items()):
        # Skip mandatory inputs and the trait methods
        if key in ('trait_added', 'trait_modified', 'in_file', 'reference',
                   'environ', 'output_type', 'out_file', 'out_matrix_file',
                   'in_matrix_file', 'apply_xfm', 'ignore_exception',
                   'terminal_output', 'out_log', 'save_log'):
            continue
        param = None
        value = None
        if key == 'args':
            param = '-v'
            value = '-v'
        elif isinstance(trait_spec.trait_type, File):
            value = tmpfile
            param = trait_spec.argstr % value
        elif trait_spec.default is False:
            param = trait_spec.argstr
            value = True
        elif key in ('searchr_x', 'searchr_y', 'searchr_z'):
            value = [-45, 45]
            param = trait_spec.argstr % ' '.join(str(elt) for elt in value)
        else:
            value = trait_spec.default
            param = trait_spec.argstr % value
        cmdline = 'flirt -in %s -ref %s' % (infile, reffile)
        # Handle autogeneration of outfile
        pth, fname, ext = split_filename(infile)
        outfile = fsl_name(fsl.FLIRT(), '%s_flirt' % fname)
        outfile = ' '.join(['-out', outfile])
        # Handle autogeneration of outmatrix
        outmatrix = '%s_flirt.mat' % fname
        outmatrix = ' '.join(['-omat', outmatrix])
        # Build command line
        cmdline = ' '.join([cmdline, outfile, outmatrix, param])
        flirter = fsl.FLIRT(in_file=infile, reference=reffile)
        setattr(flirter.inputs, key, value)
        assert flirter.cmdline == cmdline

    # Test OutputSpec
    flirter = fsl.FLIRT(in_file=infile, reference=reffile)
    pth, fname, ext = split_filename(infile)
    flirter.inputs.out_file = ''.join(['foo', ext])
    flirter.inputs.out_matrix_file = ''.join(['bar', ext])
    outs = flirter._list_outputs()
    assert outs['out_file'] == \
        os.path.join(os.getcwd(), flirter.inputs.out_file)
    assert outs['out_matrix_file'] == \
        os.path.join(os.getcwd(), flirter.inputs.out_matrix_file)


# Mcflirt
@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_mcflirt(setup_flirt):
    tmpdir, infile, reffile = setup_flirt

    frt = fsl.MCFLIRT()
    assert frt.cmd == 'mcflirt'
    # Test generated outfile name

    frt.inputs.in_file = infile
    _, nme = os.path.split(infile)
    outfile = os.path.join(os.getcwd(), nme)
    outfile = frt._gen_fname(outfile, suffix='_mcf')
    realcmd = 'mcflirt -in ' + infile + ' -out ' + outfile
    assert frt.cmdline == realcmd
    # Test specified outfile name
    outfile2 = '/newdata/bar.nii'
    frt.inputs.out_file = outfile2
    realcmd = 'mcflirt -in ' + infile + ' -out ' + outfile2
    assert frt.cmdline == realcmd

    opt_map = {
        'cost': ('-cost mutualinfo', 'mutualinfo'),
        'bins': ('-bins 256', 256),
        'dof': ('-dof 6', 6),
        'ref_vol': ('-refvol 2', 2),
        'scaling': ('-scaling 6.00', 6.00),
        'smooth': ('-smooth 1.00', 1.00),
        'rotation': ('-rotation 2', 2),
        'stages': ('-stages 3', 3),
        'init': ('-init %s' % (infile), infile),
        'use_gradient': ('-gdt', True),
        'use_contour': ('-edge', True),
        'mean_vol': ('-meanvol', True),
        'stats_imgs': ('-stats', True),
        'save_mats': ('-mats', True),
        'save_plots': ('-plots', True),
    }

    for name, settings in list(opt_map.items()):
        fnt = fsl.MCFLIRT(in_file=infile, **{name: settings[1]})
        instr = '-in %s' % (infile)
        outstr = '-out %s' % (outfile)
        if name in ('init', 'cost', 'dof', 'mean_vol', 'bins'):
            assert fnt.cmdline == ' '.join([fnt.cmd,
                                            instr,
                                            settings[0],
                                            outstr])
        else:
            assert fnt.cmdline == ' '.join([fnt.cmd,
                                            instr,
                                            outstr,
                                            settings[0]])

    # Test error is raised when missing required args
    fnt = fsl.MCFLIRT()
    with pytest.raises(ValueError):
        fnt.run()

# test fnirt


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_fnirt(setup_flirt):

    tmpdir, infile, reffile = setup_flirt
    fnirt = fsl.FNIRT()
    assert fnirt.cmd == 'fnirt'

    # Test list parameters
    params = [('subsampling_scheme', '--subsamp', [4, 2, 2, 1], '4,2,2,1'),
              ('max_nonlin_iter', '--miter', [4, 4, 4, 2], '4,4,4,2'),
              ('ref_fwhm', '--reffwhm', [4, 2, 2, 0], '4,2,2,0'),
              ('in_fwhm', '--infwhm', [4, 2, 2, 0], '4,2,2,0'),
              ('apply_refmask', '--applyrefmask', [0, 0, 1, 1], '0,0,1,1'),
              ('apply_inmask', '--applyinmask', [0, 0, 0, 1], '0,0,0,1'),
              ('regularization_lambda', '--lambda', [0.5, 0.75], '0.5,0.75')]
    for item, flag, val, strval in params:
        fnirt = fsl.FNIRT(in_file=infile,
                          ref_file=reffile,
                          **{item: val})
        log = fnirt._gen_fname(infile, suffix='_log.txt', change_ext=False)
        iout = fnirt._gen_fname(infile, suffix='_warped')
        if item in ('max_nonlin_iter'):
            cmd = 'fnirt --in=%s '\
                  '--logout=%s'\
                  ' %s=%s --ref=%s'\
                  ' --iout=%s' % (infile, log,
                                  flag, strval, reffile, iout)
        elif item in ('in_fwhm'):
            cmd = 'fnirt --in=%s %s=%s --logout=%s '\
                  '--ref=%s --iout=%s' % (infile, flag,
                                          strval, log, reffile, iout)
        elif item.startswith('apply'):
            cmd = 'fnirt %s=%s '\
                  '--in=%s '\
                  '--logout=%s '\
                  '--ref=%s --iout=%s' % (flag, strval,
                                          infile, log,
                                          reffile,
                                          iout)

        else:
            cmd = 'fnirt '\
                  '--in=%s --logout=%s '\
                  '--ref=%s %s=%s --iout=%s' % (infile, log,
                                                reffile,
                                                flag, strval,
                                                iout)
        assert fnirt.cmdline == cmd

    # Test ValueError is raised when missing mandatory args
    fnirt = fsl.FNIRT()
    with pytest.raises(ValueError):
        fnirt.run()
    fnirt.inputs.in_file = infile
    fnirt.inputs.ref_file = reffile

    # test files
    opt_map = {
        'affine_file': ('--aff='),
        'inwarp_file': ('--inwarp='),
        'in_intensitymap_file': ('--intin='),
        'config_file': ('--config='),
        'refmask_file': ('--refmask='),
        'inmask_file': ('--inmask='),
        'field_file': ('--fout='),
        'jacobian_file': ('--jout='),
        'modulatedref_file': ('--refout='),
        'out_intensitymap_file': ('--intout='),
        'log_file': ('--logout=')}

    for name, settings in list(opt_map.items()):
        fnirt = fsl.FNIRT(in_file=infile,
                          ref_file=reffile,
                          **{name: infile})

        if name in ('config_file', 'affine_file', 'field_file'):
            cmd = 'fnirt %s%s --in=%s '\
                  '--logout=%s '\
                  '--ref=%s --iout=%s' % (settings, infile, infile, log,
                                          reffile, iout)
        elif name in ('refmask_file'):
            cmd = 'fnirt --in=%s '\
                  '--logout=%s --ref=%s '\
                  '%s%s '\
                  '--iout=%s' % (infile, log,
                                 reffile,
                                 settings, infile,
                                 iout)
        elif name in ('in_intensitymap_file', 'inwarp_file', 'inmask_file', 'jacobian_file'):
            cmd = 'fnirt --in=%s '\
                  '%s%s '\
                  '--logout=%s --ref=%s '\
                  '--iout=%s' % (infile,
                                 settings, infile,
                                 log,
                                 reffile,
                                 iout)
        elif name in ('log_file'):
            cmd = 'fnirt --in=%s '\
                  '%s%s --ref=%s '\
                  '--iout=%s' % (infile,
                                 settings, infile,
                                 reffile,
                                 iout)
        else:
            cmd = 'fnirt --in=%s '\
                  '--logout=%s %s%s '\
                  '--ref=%s --iout=%s' % (infile, log,
                                          settings, infile,
                                          reffile, iout)

        assert fnirt.cmdline == cmd


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_applywarp(setup_flirt):
    tmpdir, infile, reffile = setup_flirt
    opt_map = {
        'out_file': ('--out=bar.nii', 'bar.nii'),
        'premat': ('--premat=%s' % (reffile), reffile),
        'postmat': ('--postmat=%s' % (reffile), reffile),
    }

    # in_file, ref_file, field_file mandatory
    for name, settings in list(opt_map.items()):
        awarp = fsl.ApplyWarp(in_file=infile,
                              ref_file=reffile,
                              field_file=reffile,
                              **{name: settings[1]})
        if name == 'out_file':
            realcmd = 'applywarp --in=%s '\
                      '--ref=%s --out=%s '\
                      '--warp=%s' % (infile, reffile,
                                     settings[1], reffile)
        else:
            outfile = awarp._gen_fname(infile, suffix='_warp')
            realcmd = 'applywarp --in=%s '\
                      '--ref=%s --out=%s '\
                      '--warp=%s %s' % (infile, reffile,
                                        outfile, reffile,
                                        settings[0])
        assert awarp.cmdline == realcmd


@pytest.fixture()
def setup_fugue(tmpdir):
    import nibabel as nb
    import numpy as np
    import os.path as op

    d = np.ones((80, 80, 80))
    tmp_dir = str(tmpdir)
    infile = op.join(tmp_dir, 'dumbfile.nii.gz')
    nb.Nifti1Image(d, None, None).to_filename(infile)

    return (tmp_dir, infile)


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
@pytest.mark.parametrize("attr, out_file", [
        ({"save_unmasked_fmap":True, "fmap_in_file":"infile", "mask_file":"infile", "output_type":"NIFTI_GZ"},
         'fmap_out_file'),
        ({"save_unmasked_shift":True, "fmap_in_file":"infile", "dwell_time":1.e-3, "mask_file":"infile", "output_type": "NIFTI_GZ"},
         "shift_out_file"),
        ({"in_file":"infile", "mask_file":"infile", "shift_in_file":"infile", "output_type":"NIFTI_GZ"},
         'unwarped_file')
        ])
def test_fugue(setup_fugue, attr, out_file):
    import os.path as op
    tmpdir, infile = setup_fugue

    fugue = fsl.FUGUE()
    for key, value in attr.items():
        if value == "infile": setattr(fugue.inputs, key, infile)
        else: setattr(fugue.inputs, key, value)
    res = fugue.run()

    assert isdefined(getattr(res.outputs,out_file))
    trait_spec = fugue.inputs.trait(out_file)
    out_name = trait_spec.name_template % 'dumbfile'
    out_name += '.nii.gz'
    assert op.basename(getattr(res.outputs, out_file)) == out_name


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_first_genfname():
    first = fsl.FIRST()
    first.inputs.out_file = 'segment.nii'
    first.inputs.output_type = "NIFTI_GZ"

    value = first._gen_fname(name='original_segmentations')
    expected_value = os.path.abspath('segment_all_fast_origsegs.nii.gz')
    assert value == expected_value
    first.inputs.method = 'none'
    value = first._gen_fname(name='original_segmentations')
    expected_value = os.path.abspath('segment_all_none_origsegs.nii.gz')
    assert value == expected_value
    first.inputs.method = 'auto'
    first.inputs.list_of_specific_structures = ['L_Hipp', 'R_Hipp']
    value = first._gen_fname(name='original_segmentations')
    expected_value = os.path.abspath('segment_all_none_origsegs.nii.gz')
    assert value == expected_value


@pytest.mark.skipif(no_fsl(), reason="fsl is not installed")
def test_deprecation():
    interface = fsl.ApplyXfm()
    assert isinstance(interface, fsl.ApplyXFM)

