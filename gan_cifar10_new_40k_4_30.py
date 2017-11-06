import os, sys
sys.path.append(os.getcwd())

import time
import tflib as lib
import tflib.save_images
import tflib.mnist
import tflib.cifar10_all
import tflib.plot
import tflib.inception_score

import numpy as np


import torch
import torchvision
from torch import nn
from torch import autograd
from torch import optim

# Download CIFAR-10 (Python version) at
# https://www.cs.toronto.edu/~kriz/cifar.html and fill in the path to the
# extracted files here!
DATA_DIR = '/home/dxu/imageGeneration/cifar-10-batches-py/'
if len(DATA_DIR) == 0:
    raise Exception('Please specify path to data directory in gan_cifar.py!')

MODE = 'wgan-gp' # Valid options are dcgan, wgan, or wgan-gp
DIM = 128 # This overfits substantially; you're probably better off with 64
LAMBDA = 50 # Gradient penalty lambda hyperparameter
CRITIC_ITERS = 5 # How many critic iterations per generator iteration
BATCH_SIZE = 64 # Batch size
ITERS = 200000 # How many generator iterations to train for
OUTPUT_DIM = 3072 # Number of pixels in CIFAR10 (3*32*32)
inception_score_all = [];
results_save = './results_new/cifar10_4_30'
if not os.path.isdir(results_save):
    os.makedirs(results_save);

# SP parameters --------------------
r_1 = 0.5
SP_begin = 0.025
SP_end = 0.8
n_SP_iter = 5 # number of self-paced iterations
Scores = []
# ----------------------------------

class Generator(nn.Module):
    def __init__(self):
        super(Generator, self).__init__()
        preprocess = nn.Sequential(
            nn.Linear(128, 4 * 4 * 4 * DIM),
            nn.BatchNorm2d(4 * 4 * 4 * DIM),
            nn.ReLU(True),
        )

        block1 = nn.Sequential(
            nn.ConvTranspose2d(4 * DIM, 2 * DIM, 2, stride=2),
            nn.BatchNorm2d(2 * DIM),
            nn.ReLU(True),
        )
        block2 = nn.Sequential(
            nn.ConvTranspose2d(2 * DIM, DIM, 2, stride=2),
            nn.BatchNorm2d(DIM),
            nn.ReLU(True),
        )
        deconv_out = nn.ConvTranspose2d(DIM, 3, 2, stride=2)

        self.preprocess = preprocess
        self.block1 = block1
        self.block2 = block2
        self.deconv_out = deconv_out
        self.tanh = nn.Tanh()

    def forward(self, input):
        output = self.preprocess(input)
        output = output.view(-1, 4 * DIM, 4, 4)
        output = self.block1(output)
        output = self.block2(output)
        output = self.deconv_out(output)
        output = self.tanh(output)
        return output.view(-1, 3, 32, 32)


class Discriminator(nn.Module):
    def __init__(self):
        super(Discriminator, self).__init__()
        main = nn.Sequential(
            nn.Conv2d(3, DIM, 3, 2, padding=1),
            nn.LeakyReLU(),
            nn.Conv2d(DIM, 2 * DIM, 3, 2, padding=1),
            nn.LeakyReLU(),
            nn.Conv2d(2 * DIM, 4 * DIM, 3, 2, padding=1),
            nn.LeakyReLU(),
        )

        self.main = main
        self.linear = nn.Linear(4*4*4*DIM, 1)

    def forward(self, input):
        output = self.main(input)
        output = output.view(-1, 4*4*4*DIM)
        output = self.linear(output)
        return output

netG = Generator()
netD = Discriminator()
print netG
print netD

use_cuda = torch.cuda.is_available()
if use_cuda:
    gpu = 7
if use_cuda:
    netD = netD.cuda(gpu)
    netG = netG.cuda(gpu)

one = torch.FloatTensor([1])
mone = one * -1
if use_cuda:
    one = one.cuda(gpu)
    mone = mone.cuda(gpu)

optimizerD = optim.Adam(netD.parameters(), lr=1e-4, betas=(0.5, 0.9))
optimizerG = optim.Adam(netG.parameters(), lr=1e-4, betas=(0.5, 0.9))

netD_old = netD
netG_old = netG
if use_cuda:
    netD_old = netD_old.cuda(gpu)
    netG_old = netG_old.cuda(gpu)

def calc_gradient_penalty(netD, real_data, fake_data):
    # print "real_data: ", real_data.size(), fake_data.size()
    alpha = torch.rand(BATCH_SIZE, 1)
    alpha = alpha.expand(BATCH_SIZE, real_data.nelement()/BATCH_SIZE).contiguous().view(BATCH_SIZE, 3, 32, 32)
    alpha = alpha.cuda(gpu) if use_cuda else alpha

    interpolates = alpha * real_data + ((1 - alpha) * fake_data)

    if use_cuda:
        interpolates = interpolates.cuda(gpu)
    interpolates = autograd.Variable(interpolates, requires_grad=True)

    disc_interpolates = netD(interpolates)

    gradients = autograd.grad(outputs=disc_interpolates, inputs=interpolates,
                              grad_outputs=torch.ones(disc_interpolates.size()).cuda(gpu) if use_cuda else torch.ones(
                                  disc_interpolates.size()),
                              create_graph=True, retain_graph=True, only_inputs=True)[0]

    gradient_penalty = ((gradients.norm(2, dim=1) - 1) ** 2).mean() * LAMBDA
    return gradient_penalty

# For generating samples
def generate_image(frame, netG):
    fixed_noise_128 = torch.randn(128, 128)
    if use_cuda:
        fixed_noise_128 = fixed_noise_128.cuda(gpu)
    noisev = autograd.Variable(fixed_noise_128, volatile=True)
    samples = netG(noisev)
    samples = samples.view(-1, 3, 32, 32)
    samples = samples.mul(0.5).add(0.5)
    samples = samples.cpu().data.numpy()

    lib.save_images.save_images(samples, (results_save + '/samples_{}.jpg').format(frame))

# For calculating inception score
def get_inception_score(G, ):
    all_samples = []
    for i in xrange(10):
        samples_100 = torch.randn(100, 128)
        if use_cuda:
            samples_100 = samples_100.cuda(gpu)
        samples_100 = autograd.Variable(samples_100, volatile=True)
        all_samples.append(G(samples_100).cpu().data.numpy())

    all_samples = np.concatenate(all_samples, axis=0)
    all_samples = np.multiply(np.add(np.multiply(all_samples, 0.5), 0.5), 255).astype('int32')
    all_samples = all_samples.reshape((-1, 3, 32, 32)).transpose(0, 2, 3, 1)
    return lib.inception_score.get_inception_score(list(all_samples))

# Dataset iterator
#train_gen, dev_gen = lib.cifar10.load(BATCH_SIZE, data_dir=DATA_DIR)
eval_gen, dev_gen = lib.cifar10_all.load(BATCH_SIZE, DATA_DIR, Scores, 1, 1)
train_gen, dev_gen = lib.cifar10_all.load(BATCH_SIZE, DATA_DIR, Scores, 1, 0)
def inf_train_gen():
    while True:
        for images in train_gen():
            # yield images.astype('float32').reshape(BATCH_SIZE, 3, 32, 32).transpose(0, 2, 3, 1)
            yield images
gen = inf_train_gen()
preprocess = torchvision.transforms.Compose([
                               torchvision.transforms.ToTensor(),
                               torchvision.transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
                           ])

# lines that i've changed -----------------------------------------------------------------------
r_t = r_1 
SP_iter_begin = np.round(ITERS * SP_begin)						   
SP_iter_end = np.round(ITERS * SP_end)	
tot_SP_iter = SP_iter_end - SP_iter_begin

r = r_1
s = 0
for t in range(1, n_SP_iter+1):
    s = s + r
    r = r + (1-r_1) / n_SP_iter
	
r = r_1
next_eval_iter = np.zeros(n_SP_iter+2)
next_eval_iter[1] = SP_iter_begin
for t in range(2, n_SP_iter + 1):
    next_eval_iter[t] = next_eval_iter[t-1] + np.round(tot_SP_iter * (r / s))
    r = r + (1-r_1) / n_SP_iter

next_eval_iter[n_SP_iter+1] = SP_iter_end + 1
t = 1

iter_1 = 0
old_IS = 0
						   
for iteration in xrange(ITERS):
    start_time = time.time()
    ########################################################################################################
    ############################################ SP ##################################################

    if iter_1 >= SP_iter_begin and iter_1 < SP_iter_end:

        # compute scores for each real sample image at every SP iteration -------------
        if iter_1  == next_eval_iter[t]:
		
		# Calculate inception score 
		inception_score = get_inception_score(netG)
		inception_score_all = np.append(inception_score_all, inception_score[0]);
		lib.plot.plot(results_save + '/inception score', inception_score[0])
			
		if inception_score[0] < old_IS:
			# restore the old status
			netD = netD_old
			netG = netG_old
			iter_1 = next_eval_iter[t-1]
		else: 
			netD_old = netD
			netG_old = netG
			old_IS = inception_score[0]				
			t = t + 1 

				
		Scores = []
		for images in eval_gen():
			images = images.reshape(BATCH_SIZE, 3, 32, 32).transpose(0, 2, 3, 1)
			imgs = torch.stack([preprocess(item) for item in images])

			# imgs = preprocess(images)
			if use_cuda:
				imgs = imgs.cuda(gpu)
			imgs_v = autograd.Variable(imgs, volatile=True)

			D = netD(imgs_v)
			batch_scores = D.cpu().data.numpy().flatten()
			Scores = np.concatenate((Scores, batch_scores), axis=0)
			
			
		r_t = r_t + (1-r_1) / n_SP_iter
		#Scores = (-1) * Scores
		train_gen, dev_gen = lib.cifar10_all.load(BATCH_SIZE, DATA_DIR, Scores, r_t, 0)
		gen = inf_train_gen();
				
    ########################################################################################################

    iter_1 = iter_1 + 1 # this should be intended EXTERNALLY to the "if iter_1 >= SP_iter_begin and iter_1 < SP_iter_end:"

    ############################
    # (1) Update D network
    ###########################
    for p in netD.parameters():  # reset requires_grad
        p.requires_grad = True  # they are set to False below in netG update
    for i in xrange(CRITIC_ITERS):
        _data = gen.next()
        netD.zero_grad()

        # train with real
        _data = _data.reshape(BATCH_SIZE, 3, 32, 32).transpose(0, 2, 3, 1)
        real_data = torch.stack([preprocess(item) for item in _data])

        if use_cuda:
            real_data = real_data.cuda(gpu)
        real_data_v = autograd.Variable(real_data)

        # import torchvision
        # filename = os.path.join("test_train_data", str(iteration) + str(i) + ".jpg")
        # torchvision.utils.save_image(real_data, filename)

        D_real = netD(real_data_v)
        D_real = D_real.mean()
        D_real.backward(mone)

        # train with fake
        noise = torch.randn(BATCH_SIZE, 128)
        if use_cuda:
            noise = noise.cuda(gpu)
        noisev = autograd.Variable(noise, volatile=True)  # totally freeze netG
        fake = autograd.Variable(netG(noisev).data)
        inputv = fake
        D_fake = netD(inputv)
        D_fake = D_fake.mean()
        D_fake.backward(one)

        # train with gradient penalty
        gradient_penalty = calc_gradient_penalty(netD, real_data_v.data, fake.data)
        gradient_penalty.backward()

        # print "gradien_penalty: ", gradient_penalty

        D_cost = D_fake - D_real + gradient_penalty
        Wasserstein_D = D_real - D_fake
        optimizerD.step()
    ############################
    # (2) Update G network
    ###########################
    for p in netD.parameters():
        p.requires_grad = False  # to avoid computation
    netG.zero_grad()

    noise = torch.randn(BATCH_SIZE, 128)
    if use_cuda:
        noise = noise.cuda(gpu)
    noisev = autograd.Variable(noise)
    fake = netG(noisev)
    G = netD(fake)
    G = G.mean()
    G.backward(mone)
    G_cost = -G
    optimizerG.step()

    # Write logs and save samples
    lib.plot.plot(results_save + '/train disc cost', D_cost.cpu().data.numpy())
    lib.plot.plot(results_save + '/time', time.time() - start_time)
    lib.plot.plot(results_save + '/train gen cost', G_cost.cpu().data.numpy())
    lib.plot.plot(results_save + '/wasserstein distance', Wasserstein_D.cpu().data.numpy())

    # Calculate inception score every 15K iters after the self-paced process
    if iter_1 > SP_iter_end and iteration % 15000 == 14999:
        inception_score = get_inception_score(netG)
        inception_score_all = np.append(inception_score_all, inception_score[0]);
        lib.plot.plot(results_save + '/inception score', inception_score[0])

    # Calculate dev loss and generate samples every 100 iters
    if iteration % 100 == 99:
        dev_disc_costs = []
        for images in dev_gen():
            images = images.reshape(BATCH_SIZE, 3, 32, 32).transpose(0, 2, 3, 1)
            imgs = torch.stack([preprocess(item) for item in images])

            # imgs = preprocess(images)
            if use_cuda:
                imgs = imgs.cuda(gpu)
            imgs_v = autograd.Variable(imgs, volatile=True)

            D = netD(imgs_v)
            _dev_disc_cost = -D.mean().cpu().data.numpy()
            dev_disc_costs.append(_dev_disc_cost)
        lib.plot.plot(results_save + '/dev disc cost', np.mean(dev_disc_costs))

        generate_image(iteration, netG)

    # Save logs every 100 iters
    if (iteration < 5) or (iteration % 100 == 99):
        lib.plot.flush()
    lib.plot.tick()
print inception_score_all
np.savetxt(results_save + '/inception_score.txt', inception_score_all, delimiter=',');
