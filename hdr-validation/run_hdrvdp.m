% run_hdrvdp.m TEST.f32 REF.f32 W H
% Prints one line: HDRVDP_Q_JOD=<value> Q=<value>
args = argv();
tname = args{1}; rname = args{2};
W = str2double(args{3}); H = str2double(args{4});
pkg load image;
pkg load statistics;
warning('off', 'all');
addpath(genpath('hdrvdp-3.0.7'));
readf32 = @(p) permute(reshape(fread(fopen(p, 'rb'), Inf, 'single'), [W H 3]), [2 1 3]);
T = readf32(tname); R = readf32(rname);
% BT.2100 recommended UHD viewing distance of 1.6 picture heights => ~62 ppd
ppd = 62;
res = hdrvdp3('quality', T, R, 'rgb-bt.2020', ppd, {'use_gpu', false, 'quiet', true});
printf('HDRVDP_Q_JOD=%.6f Q=%.6f\n', res.Q_JOD, res.Q);
